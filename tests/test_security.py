from datetime import timedelta
import unittest
from unittest import mock

from fishtank.api.common import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from fishtank.db import utcnow
from fishtank.models import rate_limit
from fishtank.models.fishtank_record import FishtankFish, FishtankRecord
from fishtank.models.user import AuthToken, User
from tests.api_test_case import PREFIX, ApiTestCase

# Tests for the web ui's session cookie and csrf token, rate limits, changing the password,
# removing an account and the security headers
# Run from the project root: python -m unittest tests.test_security -v


def set_cookie_headers(response):
    return {header.split('=', 1)[0]: header for header in response.headers.getlist('Set-Cookie')}


class BrowserTestCase(ApiTestCase):

    def setUp(self):
        super().setUp()
        # a client that keeps cookies, like the web ui in a browser
        self.browser = self.app.test_client()

    def browse(self, method, path, json=None, csrf=True, expected_status=None, ip='127.0.0.1'):
        headers = {}
        cookie = self.browser.get_cookie(CSRF_COOKIE)
        if csrf and cookie is not None:
            headers[CSRF_HEADER] = cookie.value
        response = self.browser.open(PREFIX + path, method=method, json=json, headers=headers,
                                     environ_base={'REMOTE_ADDR': ip})
        if expected_status is not None:
            self.assertEqual(response.status_code, expected_status, response.get_json())
        return response

    def browser_login(self, username='alice', password='correct horse', expected_status=200):
        return self.browse('POST', '/auth/login', {'username': username, 'password': password},
                           expected_status=expected_status)

    def from_ip(self, ip, method, path, json=None, token=None, expected_status=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        response = self.client.open(PREFIX + path, method=method, json=json, headers=headers,
                                    environ_base={'REMOTE_ADDR': ip})
        if expected_status is not None:
            self.assertEqual(response.status_code, expected_status, response.get_json())
        return response


class SessionCookieTest(BrowserTestCase):

    def test_login_sets_an_http_only_session_cookie_and_a_readable_csrf_cookie(self):
        self.register()
        cookies = set_cookie_headers(self.browser_login())
        session = cookies[SESSION_COOKIE]
        for flag in ('HttpOnly', 'Secure', 'SameSite=Lax', 'Path=/fishtank_api'):
            self.assertIn(flag, session)
        csrf = cookies[CSRF_COOKIE]
        self.assertIn('Secure', csrf)
        self.assertIn('SameSite=Lax', csrf)
        self.assertNotIn('HttpOnly', csrf)

    def test_register_logs_the_browser_in(self):
        self.browse('POST', '/auth/register', {'username': 'alice', 'password': 'correct horse'}, expected_status=201)
        me = self.browse('GET', '/auth/me', expected_status=200).get_json()['user']
        self.assertEqual(me['username'], 'alice')

    def test_the_cookie_carries_the_login(self):
        self.register()
        self.browser_login()
        self.assertEqual(self.browse('GET', '/auth/me', expected_status=200).get_json()['user']['username'], 'alice')
        key = self.browse('POST', '/fishtanks', {}, expected_status=201).get_json()['fishtank']['key']
        self.assertTrue(FishtankRecord.get(FishtankRecord.key == key).owner_id)

    def test_secure_flag_can_be_turned_off_for_plain_http(self):
        self.app.config['FISHTANK_SECURE_COOKIES'] = False
        self.register()
        cookies = set_cookie_headers(self.browser_login())
        self.assertNotIn('Secure', cookies[SESSION_COOKIE])
        self.assertIn('HttpOnly', cookies[SESSION_COOKIE])

    def test_logout_clears_the_cookies_and_ends_the_login(self):
        self.register()
        self.browser_login()
        token = self.browser.get_cookie(SESSION_COOKIE, path='/fishtank_api').value
        response = self.browse('POST', '/auth/logout', expected_status=200)
        for name in (SESSION_COOKIE, CSRF_COOKIE):
            self.assertIn('Max-Age=0', set_cookie_headers(response)[name])
        self.assertIsNone(self.browser.get_cookie(SESSION_COOKIE, path='/fishtank_api'))
        self.call('GET', '/auth/me', token=token, expected_status=401)

    def test_an_expired_cookie_is_refused_and_cleared(self):
        self.register()
        self.browser_login()
        AuthToken.update(expires_at=utcnow() - timedelta(seconds=1)).execute()
        response = self.browse('GET', '/auth/me', expected_status=401)
        self.assertIn('Max-Age=0', set_cookie_headers(response)[SESSION_COOKIE])
        # the next request is a visitor's
        self.browse('GET', '/fish', expected_status=200)
        self.browse('GET', '/auth/me', expected_status=401)

    def test_an_expired_cookie_does_not_keep_anyone_from_logging_in(self):
        self.register()
        self.browser_login()
        AuthToken.delete().execute()
        self.browser_login()
        self.browse('GET', '/auth/me', expected_status=200)

    def test_bearer_tokens_still_work_and_win_over_the_cookie(self):
        alice = self.register()
        self.register('bob')
        self.browser_login('bob')
        response = self.browser.get(PREFIX + '/auth/me', headers={'Authorization': 'Bearer ' + alice})
        self.assertEqual(response.get_json()['user']['username'], 'alice')


class CsrfTest(BrowserTestCase):

    def setUp(self):
        super().setUp()
        self.register()
        self.browser_login()

    def test_changes_without_the_csrf_token_are_refused(self):
        response = self.browse('POST', '/fishtanks', {}, csrf=False, expected_status=403)
        self.assertIn('csrf', response.get_json()['message'])
        self.assertEqual(FishtankRecord.select().count(), 0)
        self.browse('POST', '/auth/logout', csrf=False, expected_status=403)
        self.browse('GET', '/auth/me', expected_status=200)

    def test_a_wrong_csrf_token_is_refused(self):
        response = self.browser.post(PREFIX + '/fishtanks', json={}, headers={CSRF_HEADER: 'made up'})
        self.assertEqual(response.status_code, 403)

    def test_the_csrf_token_of_another_login_is_refused(self):
        other = self.app.test_client()
        other.post(PREFIX + '/auth/login', json={'username': 'alice', 'password': 'correct horse'})
        response = self.browser.post(PREFIX + '/fishtanks', json={},
                                     headers={CSRF_HEADER: other.get_cookie(CSRF_COOKIE).value})
        self.assertEqual(response.status_code, 403)

    def test_reading_needs_no_csrf_token(self):
        self.browse('GET', '/fishtanks', csrf=False, expected_status=200)

    def test_bearer_requests_need_no_csrf_token(self):
        token = self.call('POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'}).get_json()['token']
        self.call('POST', '/fishtanks', {}, token=token, expected_status=201)

    def test_visitors_need_no_csrf_token(self):
        self.call('POST', '/fishtanks', {}, expected_status=201)


class LoginRateLimitTest(BrowserTestCase):

    def fail_login(self, username='alice', ip='127.0.0.1', expected_status=401):
        return self.from_ip(ip, 'POST', '/auth/login', {'username': username, 'password': 'wrong password'},
                            expected_status=expected_status)

    def test_failed_logins_are_limited_per_username(self):
        self.register()
        for attempt in range(rate_limit.FAILED_LOGINS_PER_USERNAME.limit):
            self.fail_login(ip='10.0.0.{}'.format(attempt))
        response = self.fail_login(ip='10.0.1.1', expected_status=429)
        self.assertIn('Too many failed logins', response.get_json()['message'])
        self.assertTrue(0 < int(response.headers['Retry-After']) <= 15 * 60)
        # the right password does not help once the limit is reached, nor another spelling of the username
        self.from_ip('10.0.1.1', 'POST', '/auth/login', {'username': 'ALICE', 'password': 'correct horse'},
                     expected_status=429)
        # other users can still log in
        self.register('bob')
        self.from_ip('10.0.1.1', 'POST', '/auth/login', {'username': 'bob', 'password': 'correct horse'},
                     expected_status=200)

    def test_failed_logins_are_limited_per_ip(self):
        for attempt in range(rate_limit.FAILED_LOGINS_PER_IP.limit):
            self.fail_login('user{}'.format(attempt), ip='10.0.0.1')
        self.fail_login('someone_else', ip='10.0.0.1', expected_status=429)
        self.fail_login('someone_else', ip='10.0.0.2', expected_status=401)

    def test_the_limit_ends_after_the_window(self):
        self.register()
        for _ in range(rate_limit.FAILED_LOGINS_PER_USERNAME.limit):
            self.fail_login()
        self.fail_login(expected_status=429)
        later = utcnow() + rate_limit.FAILED_LOGINS_PER_USERNAME.window + timedelta(seconds=1)
        with mock.patch.object(rate_limit, 'utcnow', return_value=later):
            self.from_ip('127.0.0.1', 'POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'},
                         expected_status=200)

    def test_logging_in_resets_the_failures_of_the_username(self):
        self.register()
        for _ in range(rate_limit.FAILED_LOGINS_PER_USERNAME.limit - 1):
            self.fail_login()
        self.from_ip('127.0.0.1', 'POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'},
                     expected_status=200)
        for _ in range(rate_limit.FAILED_LOGINS_PER_USERNAME.limit):
            self.fail_login()

    def test_registrations_are_limited_per_ip(self):
        for attempt in range(rate_limit.REGISTRATIONS_PER_IP.limit):
            self.from_ip('10.0.0.1', 'POST', '/auth/register', {'username': 'user{}'.format(attempt),
                                                                'password': 'correct horse'}, expected_status=201)
        response = self.from_ip('10.0.0.1', 'POST', '/auth/register',
                                {'username': 'one_more', 'password': 'correct horse'}, expected_status=429)
        self.assertIn('Retry-After', response.headers)
        self.from_ip('10.0.0.2', 'POST', '/auth/register', {'username': 'one_more', 'password': 'correct horse'},
                     expected_status=201)


class VisitorTankRateLimitTest(BrowserTestCase):

    def test_visitor_tanks_are_limited_per_ip(self):
        for _ in range(rate_limit.VISITOR_TANKS_PER_IP.limit):
            self.from_ip('10.0.0.1', 'POST', '/fishtanks', expected_status=201)
        response = self.from_ip('10.0.0.1', 'POST', '/fishtanks', expected_status=429)
        self.assertIn('log in to build more', response.get_json()['message'])
        self.assertTrue(0 < int(response.headers['Retry-After']) <= 3600)
        self.from_ip('10.0.0.2', 'POST', '/fishtanks', expected_status=201)

    def test_logged_in_users_are_not_limited(self):
        token = self.register()
        for _ in range(rate_limit.VISITOR_TANKS_PER_IP.limit + 1):
            self.from_ip('10.0.0.1', 'POST', '/fishtanks', token=token, expected_status=201)
        self.from_ip('10.0.0.1', 'POST', '/fishtanks', expected_status=201)


class PasswordChangeTest(BrowserTestCase):

    def change(self, token, current, new, expected_status):
        return self.call('POST', '/auth/password', {'current_password': current, 'new_password': new}, token=token,
                         expected_status=expected_status)

    def test_changing_the_password_ends_every_other_login(self):
        this_device = self.register()
        other_device = self.call('POST', '/auth/login',
                                 {'username': 'alice', 'password': 'correct horse'}).get_json()['token']
        self.change(this_device, 'correct horse', 'battery staple', 200)
        self.call('GET', '/auth/me', token=this_device, expected_status=200)
        self.call('GET', '/auth/me', token=other_device, expected_status=401)
        self.call('POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'}, expected_status=401)
        self.call('POST', '/auth/login', {'username': 'alice', 'password': 'battery staple'}, expected_status=200)

    def test_the_browser_stays_logged_in(self):
        self.register()
        self.browser_login()
        self.browse('POST', '/auth/password', {'current_password': 'correct horse', 'new_password': 'battery staple'},
                    expected_status=200)
        self.browse('GET', '/auth/me', expected_status=200)

    def test_a_wrong_current_password_is_refused(self):
        token = self.register()
        response = self.change(token, 'wrong password', 'battery staple', 403)
        self.assertEqual(response.get_json()['field'], 'current_password')
        self.call('POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'}, expected_status=200)

    def test_the_new_password_must_be_long_enough(self):
        token = self.register()
        response = self.change(token, 'correct horse', 'short', 400)
        self.assertEqual(response.get_json()['field'], 'new_password')

    def test_wrong_current_passwords_count_as_failed_logins(self):
        token = self.register()
        for _ in range(rate_limit.FAILED_LOGINS_PER_USERNAME.limit):
            self.change(token, 'wrong password', 'battery staple', 403)
        response = self.change(token, 'correct horse', 'battery staple', 429)
        self.assertIn('Retry-After', response.headers)

    def test_needs_a_login(self):
        self.call('POST', '/auth/password', {'current_password': 'x', 'new_password': 'battery staple'},
                  expected_status=401)


class AccountDeletionTest(BrowserTestCase):

    def test_removing_the_account_removes_its_logins_and_fishtanks(self):
        token = self.register()
        other_user = self.register('bob')
        key = self.new_tank(token)
        self.operate('add', key, [1, 1], token=token)
        bobs_tank = self.new_tank(other_user)
        visitor_tank = self.new_tank()
        self.call('DELETE', '/auth/me', {'password': 'correct horse'}, token=token, expected_status=200)
        self.assertIsNone(User.get_or_none(User.username == 'alice'))
        self.call('GET', '/auth/me', token=token, expected_status=401)
        self.assertEqual([record.key for record in FishtankRecord.select().order_by(FishtankRecord.id)],
                         [bobs_tank, visitor_tank])
        self.assertEqual(FishtankFish.select().join(FishtankRecord).where(FishtankRecord.key == key).count(), 0)
        self.assertEqual(AuthToken.select().count(), 1)
        self.call('POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'}, expected_status=401)
        self.register()

    def test_the_browser_is_logged_out(self):
        self.register()
        self.browser_login()
        response = self.browse('DELETE', '/auth/me', {'password': 'correct horse'}, expected_status=200)
        self.assertIn('Max-Age=0', set_cookie_headers(response)[SESSION_COOKIE])
        self.browse('GET', '/auth/me', expected_status=401)

    def test_a_wrong_password_keeps_the_account(self):
        token = self.register()
        response = self.call('DELETE', '/auth/me', {'password': 'wrong password'}, token=token, expected_status=403)
        self.assertEqual(response.get_json()['field'], 'password')
        self.call('DELETE', '/auth/me', {}, token=token, expected_status=400)
        self.call('GET', '/auth/me', token=token, expected_status=200)

    def test_the_last_admin_cannot_remove_themselves(self):
        admin = self.register_admin()
        response = self.call('DELETE', '/auth/me', {'password': 'correct horse'}, token=admin, expected_status=409)
        self.assertIn('last admin', response.get_json()['message'])
        self.call('GET', '/auth/me', token=admin, expected_status=200)

    def test_an_admin_can_leave_when_another_admin_stays(self):
        admin = self.register_admin()
        self.register_admin('second_admin')
        self.call('DELETE', '/auth/me', {'password': 'correct horse'}, token=admin, expected_status=200)
        self.assertEqual([user.username for user in User.select()], ['second_admin'])


class SecurityHeadersTest(ApiTestCase):

    def assert_security_headers(self, response):
        policy = response.headers['Content-Security-Policy']
        for directive in ("default-src 'self'", "script-src 'self'", "frame-ancestors 'none'",
                          'https://fonts.googleapis.com', 'https://fonts.gstatic.com'):
            self.assertIn(directive, policy)
        self.assertNotIn('unsafe-inline', policy)
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')

    def test_every_answer_carries_the_security_headers(self):
        for response in (self.call('GET', '/fish?group_by=family'), self.call('GET', '/fishtanks/nope'),
                         self.call('GET', '/auth/me', token='wrong'), self.client.get('/')):
            with self.subTest(path=response.request.path, status=response.status_code):
                self.assert_security_headers(response)
                self.assertNotIn('Strict-Transport-Security', response.headers)

    def test_https_answers_ask_browsers_to_stay_on_https(self):
        response = self.client.get(PREFIX + '/fish/1', base_url='https://localhost')
        self.assertIn('max-age=', response.headers['Strict-Transport-Security'])


if __name__ == '__main__':
    unittest.main()
