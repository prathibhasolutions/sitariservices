from datetime import date
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import AllowedIP, AttendanceSession, Employee


class EmployeeLoginOtpTests(TestCase):
	def setUp(self):
		cache.clear()
		AllowedIP.objects.create(
			ip_address='0.0.0.0',
			description='GLOBAL_ALLOW_ALL',
			is_active=True,
		)
		self.employee = Employee.objects.create(
			name='Test Employee',
			mobile_number='9876543210',
			salary='15000.00',
			joining_date=date(2024, 1, 1),
			password='secret123',
		)

	def tearDown(self):
		cache.clear()

	@patch('management.views.send_otp_whatsapp', return_value=True)
	@patch('management.views.generate_otp', return_value='123456')
	def test_employee_login_sends_otp_for_valid_mobile(self, mock_generate_otp, mock_send_otp):
		response = self.client.post(reverse('login'), {'mobile': self.employee.mobile_number})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Enter 6-digit OTP')
		self.assertEqual(self.client.session.get('employee_login_otp'), '123456')
		self.assertEqual(self.client.session.get('employee_login_otp_employee'), self.employee.employee_id)
		mock_generate_otp.assert_called_once()
		mock_send_otp.assert_called_once_with(self.employee.mobile_number, '123456')

	@patch('management.views.send_otp_whatsapp', return_value=True)
	@patch('management.views.generate_otp', return_value='123456')
	def test_employee_login_verifies_otp_and_creates_attendance_session(self, mock_generate_otp, mock_send_otp):
		self.client.post(reverse('login'), {'mobile': self.employee.mobile_number})

		response = self.client.post(reverse('login'), {
			'mobile': self.employee.mobile_number,
			'otp': '123456',
		})

		self.assertRedirects(response, reverse('employee_dashboard'))
		self.assertEqual(self.client.session.get('employee_id'), self.employee.employee_id)
		self.assertIsNone(self.client.session.get('employee_login_otp'))
		self.assertEqual(AttendanceSession.objects.filter(employee=self.employee).count(), 1)
		mock_send_otp.assert_called_once_with(self.employee.mobile_number, '123456')

	@patch('management.views.send_otp_whatsapp', return_value=True)
	@patch('management.views.generate_otp', return_value='123456')
	def test_employee_login_rejects_invalid_otp(self, mock_generate_otp, mock_send_otp):
		self.client.post(reverse('login'), {'mobile': self.employee.mobile_number})

		response = self.client.post(reverse('login'), {
			'mobile': self.employee.mobile_number,
			'otp': '000000',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Invalid OTP. Please try again.')
		self.assertIsNone(self.client.session.get('employee_id'))
		self.assertEqual(AttendanceSession.objects.filter(employee=self.employee).count(), 0)
