# coding: utf-8

import base64
import json
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch
from urllib.parse import parse_qs
from uuid import uuid4

from celery import Celery
from celery import current_app
from celery.exceptions import Retry

from mixpanel.conf import settings as mp_settings
from mixpanel.tasks import EventTracker
from mixpanel.tasks import FunnelEventTracker
from mixpanel.tasks import PeopleTracker
from mixpanel.tasks import event_tracker
from mixpanel.tasks import funnel_tracker
from mixpanel.tasks import people_tracker


class TestCelery54(TestCase):
    def setUp(self):
        self.app = Celery(f'mixpanel-test-{uuid4()}', set_as_current=False)
        self.app.conf.update(
            broker_url='memory://',
            result_backend='cache+memory://',
            task_always_eager=True,
        )
        self.addCleanup(self.app.close)
        self.connection = Mock()
        self.connection.getresponse.return_value.status = 200
        self.connection.getresponse.return_value.reason = 'OK'
        self.connection.getresponse.return_value.read.return_value = b'1'
        connection_patch = patch.object(
            EventTracker, '_get_connection', return_value=self.connection,
        )
        connection_patch.start()
        self.addCleanup(connection_patch.stop)
        settings_patch = patch.multiple(
            mp_settings,
            MIXPANEL_API_TOKEN='test-token',
            MIXPANEL_DISABLE=False,
            MIXPANEL_TEST_PRIORITY=False,
        )
        settings_patch.start()
        self.addCleanup(settings_patch.stop)

    def payload(self):
        url = self.connection.request.call_args.args[1]
        query = parse_qs(url.split('?', 1)[1])
        return json.loads(base64.b64decode(query['data'][0]))

    def test_all_trackers_registered_with_preserved_names(self):
        for task_class in (EventTracker, PeopleTracker, FunnelEventTracker):
            task = self.app.tasks[task_class.name]
            self.assertIsInstance(task, task_class)
            self.assertIs(task.app, self.app)
            self.assertEqual(task.name, task_class.name)
            self.assertEqual(task.max_retries, mp_settings.MIXPANEL_MAX_RETRIES)

    def test_exports_resolve_to_current_apps_canonical_instances(self):
        previous = current_app._get_current_object()
        self.addCleanup(previous.set_current)
        self.app.set_current()
        for exported, task_class in (
            (event_tracker, EventTracker),
            (people_tracker, PeopleTracker),
            (funnel_tracker, FunnelEventTracker),
        ):
            self.assertIs(
                exported._get_current_object(), self.app.tasks[task_class.name],
            )

    def test_registration_isolated_between_apps(self):
        other = Celery(f'mixpanel-other-{uuid4()}', set_as_current=False)
        self.addCleanup(other.close)

        self.assertIsNot(
            other.tasks[EventTracker.name], self.app.tasks[EventTracker.name],
        )
        self.assertIs(other.tasks[EventTracker.name].app, other)

    def test_event_dispatch_preserves_payload(self):
        properties = {'distinct_id': 'example-user', 'customer_id': 'example-customer'}
        result = self.app.tasks[EventTracker.name].delay('example-event', properties)

        self.assertTrue(result.get())
        self.assertEqual(self.payload(), {
            'event': 'example-event',
            'properties': dict(properties, token='test-token'),
        })
        self.assertNotIn('token', properties)
        self.connection.close.assert_called_once_with()

    def test_people_dispatch_preserves_endpoint_and_payload(self):
        result = self.app.tasks[PeopleTracker.name].delay(
            'set', {'plan': 'example'}, distinct_id='example-user',
        )

        self.assertTrue(result.get())
        self.assertTrue(self.connection.request.call_args.args[1].startswith('/engage/?'))
        self.assertEqual(self.payload(), {
            '$token': 'test-token',
            '$distinct_id': 'example-user',
            '$set': {'plan': 'example'},
        })

    def test_funnel_dispatch_preserves_payload(self):
        result = self.app.tasks[FunnelEventTracker.name].delay(
            'example-funnel', 1, 'example-goal', {'distinct_id': 'example-user'},
        )

        self.assertTrue(result.get())
        self.assertEqual(self.payload(), {
            'event': mp_settings.MIXPANEL_FUNNEL_EVENT_ID,
            'properties': {
                'token': 'test-token',
                'distinct_id': 'example-user',
                'funnel': 'example-funnel',
                'step': 1,
                'goal': 'example-goal',
            },
        })

    def test_disabled_tracking_does_not_send(self):
        with patch.object(mp_settings, 'MIXPANEL_DISABLE', True):
            result = self.app.tasks[EventTracker.name].delay('example-event')

        self.assertFalse(result.get())
        self.connection.request.assert_not_called()

    def test_failed_response_retries_with_existing_delay(self):
        task = self.app.tasks[EventTracker.name]
        self.connection.getresponse.return_value.status = 503
        with patch.object(task, 'retry', side_effect=Retry()) as retry:
            with self.assertRaises(Retry):
                task.run('example-event')

        self.assertIsInstance(retry.call_args.kwargs['exc'], task.FailedEventRequest)
        self.assertEqual(
            retry.call_args.kwargs['countdown'], mp_settings.MIXPANEL_RETRY_DELAY,
        )
        self.connection.close.assert_called_once_with()

    def test_unexpected_error_is_not_swallowed(self):
        self.connection.request.side_effect = ValueError('unexpected')

        with self.assertRaisesRegex(ValueError, 'unexpected'):
            self.app.tasks[EventTracker.name].run('example-event')
