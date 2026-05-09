from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from properties.models import Property, PropertyImage, Feature


def get_property_admin_group():
    group, created = Group.objects.get_or_create(name="Property Admin")

    if created or group.permissions.count() == 0:

        models = [Property, PropertyImage, Feature]
        permissions = []

        for model in models:
            ct = ContentType.objects.get_for_model(model)

            perms = Permission.objects.filter(
                content_type=ct,
                codename__in=[
                    f"view_{model._meta.model_name}",
                    f"add_{model._meta.model_name}",
                    f"change_{model._meta.model_name}",
                ],
            )

            permissions.extend(perms)

        group.permissions.set(permissions)

    return group