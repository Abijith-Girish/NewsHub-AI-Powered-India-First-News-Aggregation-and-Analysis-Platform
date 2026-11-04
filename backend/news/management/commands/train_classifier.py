"""Train the TF-IDF + Logistic Regression category model and print metrics."""
from django.core.management.base import BaseCommand, CommandError

from news.ml.classifier import DATASET_PATH, train_model


class Command(BaseCommand):
    help = "Train the news categorization model on the curated seed corpus."

    def handle(self, *args, **options):
        if not DATASET_PATH.exists():
            raise CommandError(f"Training data not found: {DATASET_PATH}")
        self.stdout.write(f"Training on {DATASET_PATH} ...")
        metrics = train_model()

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Category classifier evaluation"))
        self.stdout.write(f"  rows           : {metrics['dataset_rows']}")
        self.stdout.write(f"  train / test   : {metrics['train_rows']} / {metrics['test_rows']}")
        self.stdout.write(f"  accuracy       : {metrics['accuracy']:.4f}")
        self.stdout.write(f"  macro F1       : {metrics['macro_f1']:.4f}")
        self.stdout.write(f"  weighted F1    : {metrics['weighted_f1']:.4f}")
        self.stdout.write("")
        self.stdout.write("  per class:")
        for label, values in metrics["per_class"].items():
            self.stdout.write(
                f"    {label:<16} P={values['precision']:.2f} "
                f"R={values['recall']:.2f} F1={values['f1']:.2f} n={values['support']}"
            )
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "These metrics come from a held-out split of the project's curated "
                "seed corpus, not a real-world benchmark."
            )
        )
        self.stdout.write(self.style.SUCCESS("Model saved to news/ml/artifacts/"))
