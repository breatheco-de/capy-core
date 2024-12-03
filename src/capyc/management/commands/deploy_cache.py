import os

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from capyc.django.cache import delete_cache, reset_cache, settings


class Command(BaseCommand):
    help = "Delete duplicate cohort users imported from old breathecode"

    def add_arguments(self, parser):
        parser.add_argument("--model", type=str, required=False, help="Specify the model to clean cache for")

    def handle(self, *args, **options):
        if not settings["is_cache_enabled"]:
            self.stdout.write(self.style.WARNING("Cache has been disabled"))
            return

        if "model" in options and options["model"]:
            delete_cache(options["model"])
            return

        reset_cache()
