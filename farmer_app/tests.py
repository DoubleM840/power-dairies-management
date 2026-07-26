from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase

from farmer_app.models import BreedingRecord, Cow, MilkRecord, Payment
from farmer_app.services import calculate_milk_deduction_eligibility, predict_next_month_milk


class ForecastingTests(TestCase):
    def test_predict_next_month_milk_uses_recent_trend(self):
        records = [
            SimpleNamespace(quantity=100),
            SimpleNamespace(quantity=120),
            SimpleNamespace(quantity=140),
        ]

        forecast = predict_next_month_milk(records)

        self.assertGreater(forecast, 140)


class BreedingRecordTests(TestCase):
    def test_expected_calving_date_is_auto_calculated(self):
        user = User.objects.create_user(username='testfarmer', password='secret123')
        cow = Cow.objects.create(farmer=user, tag='COW-001', name='Molly')

        record = BreedingRecord.objects.create(
            cow=cow,
            farmer=user,
            insemination_date=date(2024, 1, 1),
        )

        self.assertEqual(record.expected_calving_date, date(2024, 10, 9))


class DeductionEligibilityTests(TestCase):
    def test_milk_deduction_eligibility_detects_sufficient_balance(self):
        user = User.objects.create_user(username='deductionuser', password='secret123')
        MilkRecord.objects.create(
            farmer=user,
            quantity=Decimal('20'),
            fat_content=Decimal('3.6'),
            date_collected=date.today(),
            status='Approved',
        )

        eligibility = calculate_milk_deduction_eligibility(user, Decimal('500'))

        self.assertTrue(eligibility['can_use_deduction'])
        self.assertEqual(eligibility['available_balance'], Decimal('1000'))
