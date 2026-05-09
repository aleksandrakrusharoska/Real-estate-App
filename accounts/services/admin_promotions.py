import uuid

from django.conf import settings
from django.core.mail import EmailMessage


def send_admin_confirmation_email(request, profile):
    user = profile.user

    if not user.email:
        return

    token = uuid.uuid4()

    from accounts.models import AdminPromotion
    AdminPromotion.objects.filter(user=user).delete()

    promotion = AdminPromotion.objects.create(
        user=user,
        token=token
    )

    confirm_link = request.build_absolute_uri(
        f"/accounts/confirm-admin/{promotion.token}/"
    )

    subject = "Admin role confirmation"
    from_email = settings.DEFAULT_FROM_EMAIL

    html_content = f"""
    <p>An administrator has granted you admin privileges.</p>
    <p>Please confirm your access below:</p>
    <p><a href="{confirm_link}">Confirm admin access</a></p>
    """

    email = EmailMessage(
        subject,
        html_content,
        from_email,
        [user.email],
    )

    email.content_subtype = "html"
    email.send()


def send_downgrade_notification(user):
    subject = "Admin privileges revoked"

    html_content = """
    <p>Your administrator privileges have been revoked.</p>
    <p>If you believe this is a mistake, please contact support.</p>
    """

    email = EmailMessage(
        subject,
        html_content,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )

    email.content_subtype = "html"
    email.send()
