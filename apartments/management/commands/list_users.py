from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apartments.models import user_has_premium


class Command(BaseCommand):
    help = "List all users in the system"

    def handle(self, *args, **options):
        users = User.objects.all()

        self.stdout.write(self.style.SUCCESS(f"Total users: {users.count()}"))
        self.stdout.write("-" * 80)

        for user in users:
            premium_status = "Premium" if user_has_premium(user, "apartments") else "Free"
            self.stdout.write(
                f"ID: {user.id:3d} | "
                f"Username: {user.username:20s} | "
                f"Email: {user.email:30s} | "
                f"Status: {premium_status:7s} | "
                f"Active: {user.is_active} | "
                f"Date Joined: {user.date_joined.strftime('%Y-%m-%d')}"
            )
