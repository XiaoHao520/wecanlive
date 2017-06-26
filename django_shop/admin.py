from django.contrib import admin
from django.core import exceptions
from . import models as m

for model_class in m.__dict__.values():
    if model_class.__class__ == m.models.base.ModelBase \
            and not model_class._meta.abstract:
        try:
            admin.site.register(model_class)

        # except exceptions.ImproperlyConfigured as e:
        #     print(e)

        except admin.sites.AlreadyRegistered as e:
            pass
            # print(e)
