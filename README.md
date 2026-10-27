# mixpanel-celery

Asynchronous event tracking for Mixpanel

## Private PolicyStat Celery 5.4 compatibility branch

Version `0.11.0+policystat.1` is an internal build targeting exactly Celery
5.4.0 and Python >=3.8, not an upstream release. Do not publish it to PyPI or
deploy it into a Celery 4 environment.

Import `event_tracker`, `people_tracker`, or `funnel_tracker` from
`mixpanel.tasks` and dispatch through those registered task proxies. They
resolve to the current Celery application's canonical instance, with the
existing message names preserved. Ensure `mixpanel.tasks` is imported during
worker initialization. Classes remain available for inheritance and inspection;
class-bound dispatch such as `EventTracker.delay(...)` is no longer supported.

The focused compatibility tests use mocked HTTP connections and run inside
the approved VM from this checkout:

```sh
env -u DJANGO_SETTINGS_MODULE python -m unittest mixpanel.tests.test_celery54
```

Run the complete package suite with
`env -u DJANGO_SETTINGS_MODULE python -m unittest discover -s mixpanel/tests`.
Tox/Travis target Python 3.8 and 3.10 with Django 3.2.25 and Celery 5.4.0.
Python 3.10, real worker execution, and PolicyStat integration require
validation before release. Build any private
wheel inside the approved VM from an exact reviewed commit and record its full
source revision, build command/tool versions, filename, and SHA-256. Use a new
version for every changed artifact.

[![Build Status](https://travis-ci.org/winhamwr/mixpanel-celery.png?branch=master)](https://travis-ci.org/winhamwr/mixpanel-celery)

mixpanel-celery helps you use [Celery](http://celeryproject.org)
to asynchronously track your
[Mixpanel](http://mixpanel.com) events.
Waiting on HTTP requests to Mixpanel's api to complete
every time you want to record something slows you down.
Using mixpanel-celery gives you all of the Mixpanel goodness
without any of the potential performance impact.

## Works wherever Celery works

mixpanel-celery works great with Django,
but because Celery works with just python,
so does mixpanel-celery.

## But how do I do the thing?

I'll tell you how!
Have Celery running and want to asynchronously track an event?
Is your event called `my_event`?
You're in luck!

```python
from mixpanel.tasks import event_tracker

event_tracker.delay(
    'my_event',
    {'distinct_id': 1},
    token='YOUR_API_TOKEN',
)
```

Boom.
Once your Celery worker gets hold of that bad boy, it's tracked.

## Full-on Docs

Would you like to know more?
Well then you should [read the docs](http://mixpanel-celery.readthedocs.org),
[citizen](http://tvtropes.org/pmwiki/pmwiki.php/Film/StarshipTroopers).

## Contributing

We love pull requests!
Send us one, and you'll probably make Wes's day.

For details,
check out the
[contribution tips](http://mixpanel-celery.readthedocs.org/en/latest/contributing.html)
documentation.

## We like Mixpanel and Celery

This project isn't affiliated with the Mixpanel company.
Just a customer's implementation of a client for their service.
