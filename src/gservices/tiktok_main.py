import json  # noqa
import time
import traceback
import random
from requests.models import Response

from selenium.webdriver.common.action_chains import ActionChains  # type: ignore
from selenium.webdriver.common.keys import Keys  # type: ignore

from qlobot.marketplace.__base__ import Marketplace, LoginStatus, RequestStatus
# from .__base__ import Marketplace, LoginStatus, RequestStatus

import importlib.util
if importlib.util.find_spec("qlobot.webpush") is not None:
    from qlobot.webpush import Webpush

from http import client
client._MAXHEADERS = 1000


class TiktokMain(Marketplace):
    name = 'tiktok_main'
    label = 'tiktok'

    base_url = 'https://www.tiktok.com/'
    api_url = 'https://www.tiktok.com/'

    _default_headers = {
        'accept': '*/*',
        'referer': 'https://www.tiktok.com/',
    }
    _requests_timeout_second = 10

    def get_request(self, **kwargs) -> Response:
        custom_kwargs_key = ['endpoint']
        kwargs['url'] = kwargs.get(
            "url", (self.api_url + kwargs.get("endpoint", "")))
        session = kwargs.get('session', self.get_session())
        kwargs['timeout'] = kwargs.get(
            "timeout", self._requests_timeout_second)
        kwargs = {key: value for key,
                  value in kwargs.items() if key not in custom_kwargs_key}
        return session.get(**kwargs)

    def post_request(self, **kwargs) -> Response:
        custom_kwargs_key = ['endpoint']
        kwargs['url'] = kwargs.get(
            "url", (self.api_url + kwargs.get("endpoint", "")))
        session = kwargs.get('session', self.get_session())
        kwargs['timeout'] = kwargs.get(
            "timeout", self._requests_timeout_second)
        kwargs = {key: value for key,
                  value in kwargs.items() if key not in custom_kwargs_key}
        return session.post(**kwargs)

    def valid_account(self, username) -> bool:
        username_lower = username.lower()
        result_data = {}

        def check_profile(reg_status):
            if reg_status == RequestStatus.INIT_REG:
                res_account_info = self.get_request(
                    endpoint='passport/web/account/info/')
                account_info = res_account_info.json()
                # self._logger.info(f"Account info {username}: {json.dumps(account_info)}")  # noqa
                # print('account_info', json.dumps(account_info, indent=4))
                result_data['data'] = account_info.get('data', {})
            else:
                self._logger.error(
                    f"Error check valid account tiktok #{reg_status}: {username_lower}")  # noqa
        self.try_request('Tiktok:CheckProfile', check_profile)
        return self.valid_account_data(username, result_data)

    def valid_account_data(self, username, account_info) -> bool:
        username_lower = username.lower()
        result_data = {}

        def check_profile(reg_status):
            if reg_status == RequestStatus.INIT_REG:
                res_account_info = self.get_request(
                    endpoint='passport/web/account/info/')
                account_info = res_account_info.json()
                result_data['email'] = account_info.get(
                    'data', {}).get('email', '').lower()
            else:
                self._logger.error(
                    f"Error check valid account tiktok #{reg_status}: {username_lower}")  # noqa
        self.try_request('Tiktok:CheckProfile', check_profile)

        account_email = account_info.get('data', {}).get('email')
        if '@' not in username_lower:
            return account_info.get('data', {}).get('username') == username
        elif username_lower and account_email:
            return True
        elif account_email and '***' in account_email:
            email_arr = account_email.split('***')
            return (
                len(email_arr) == 2 and
                username_lower.startswith(email_arr[0]) and
                username_lower.endswith(email_arr[1])
            )
        return True

    def is_logged_in(self, username: str, **kwargs) -> dict:
        # return {
        #   'status': LoginStatus.NOT_LOGGED_IN,
        #   'message': 'Test relogin le ...',
        # }
        result_check = {
            'status': LoginStatus.NOT_LOGGED_IN,
            'message': ''
        }
        if self._username != username:
            self._username = username
            if not self.has_cookie_file():
                result_check['status'] = LoginStatus.NOT_LOGGED_IN
                result_check['message'] = 'Akun belum login.'
                return result_check

        def request_is_login(reg_status):
            if reg_status == RequestStatus.INIT_REG:
                res_is_logged_in = self.get_request(
                    endpoint='passport/web/account/info/'
                )
                is_logged_in_data = res_is_logged_in.json()
                # self._logger.info(
                #     f"checklogin {username}: {json.dumps(is_logged_in_data)}"
                # )
                # print(
                #     'is_logged_in_data',
                #     json.dumps(is_logged_in_data, indent=4)
                # )

                if is_logged_in_data.get('message') == 'success':
                    if self.valid_account_data(username, is_logged_in_data):
                        result_check['status'] = LoginStatus.IS_LOGGED_IN
                        result_check['message'] = 'Akun dalam posisi login.'
                        result_check['data'] = is_logged_in_data['data']
                    else:
                        self._logger.error(
                            f"Tiktok invalid account: {username}")
                        result_check['status'] = LoginStatus.NOT_LOGGED_IN
                        result_check['message'] = 'Akun tidak dalam posisi login.'  # noqa
                else:
                    result_check['status'] = LoginStatus.NOT_LOGGED_IN
                    result_check['message'] = 'Akun tidak dalam posisi login.'
            elif reg_status == RequestStatus.FAILED_TIMEOUT:
                result_check['status'] = LoginStatus.FAILED_TIMEOUT
                result_check['message'] = 'Connection timeout, periksa koneksi anda.'  # noqa
            elif reg_status == RequestStatus.FAILED_PARSE:
                result_check['message'] = 'Gagal megambil status login.'
                result_check['status'] = LoginStatus.FAILED_PARSE

        self.try_request('Tiktok:CheckIsLogin', request_is_login)

        return result_check

    def do_login(self, username: str, password: str, **kwargs) -> bool:
        self._process.log("Memulai login {}...".format(self.label))
        callback_notification = kwargs.get(
            'callback_notification', lambda message, options: None)
        notification_options = {
            'actions': [{
                'title': 'Close',
                'action': 'close',
            }, {
                'title': 'Resume Process',
                'action': 'resume_process',
            }],
            'data': {
                'process_id': self._process._id
            }
        }
        def show_notification(message): return callback_notification(
            message, notification_options)

        def close_notification(): return None
        if 'Webpush' in dir():
            def close_notification():  # noqa
                return Webpush.close_notification(notification_options['data'])

        self.load_driver(username=username)
        driver = self._get_driver()

        button_login_selector = "#top-right-action-bar-login-button"
        is_login_selector = f"#fixed-top-container:not(:has({button_login_selector}))"  # noqa

        try:
            # is_success_login = lambda: driver.is_element_exist(is_login_selector) # noqa
            def is_success_login():
                return driver.is_element_exist(is_login_selector)

            (i_login_action, _login_action) = driver.wait_elements_exist([
                button_login_selector,
                is_login_selector,
            ], 15)

            if i_login_action == -1:
                self._process.log("Login trigger error", 'failed')
                self._logger.error(f"Login {self.name} Trigger Error![1]")
                return False
            elif i_login_action == 1:
                self._process.log(
                    "Success: Account dalam posisi login.", 'success')
                self.save_driver_cookies()
                return True

            # open login pop up
            for i in range(0, 2):
                try:
                    driver.get_element(button_login_selector).click()
                    break
                except:  # noqa
                    time.sleep(random.randint(9, 19)/10)
            driver.wait_element_exist("#loginContainer", 5)
            (i_login_btn, _login_btn) = driver.wait_elements_exist([
                '#loginContainer [class*="DivLoginOptionContainer"]>div>div>div:nth-child(2) [data-e2e="channel-item"]',
                '#loginContainer [class*="DivLoginOptionContainer"]>div:nth-child(2) [data-e2e="channel-item"]',
            ], 5)
            if i_login_btn == -1:
                self._logger.error(f"Login {self.name} Trigger Error![1.1]")
                self.save_driver_cookies()
                return False

            _login_btn.click()
            time.sleep(random.randint(9, 19)/10)

            # note: hanya bisa login menggunakan username atau email
            (i_login_btn, _login_btn) = driver.wait_elements_exist([
                '[href="/login/phone-or-email/email"]',
                '[data-testid="tux-segmented-control"]>div:nth-child(3) [data-testid="tux-segment-item"]',
            ], 5)
            if i_login_btn == -1:
                self._logger.error(f"Login {self.name} Trigger Error![1.2]")

            _login_btn.click()
            time.sleep(random.randint(9, 19)/10)

            # input username
            username_selector = 'input[name="username"]'
            driver.get_element(username_selector).click()
            driver.get_element(username_selector).send_keys(username)
            time.sleep(random.randint(9, 19)/10)

            # input password
            password_selector = 'input[type="password"]'
            driver.get_element(password_selector).click()
            time.sleep(random.randint(9, 19)/10)
            if password:
                driver.get_element(password_selector).send_keys(password)
                time.sleep(random.randint(9, 19)/10)

                action = ActionChains(driver)
                action.send_keys(Keys.ENTER).perform()
                time.sleep(random.randint(9, 19)/10)
            else:
                messages = [
                    "Membutuhkan password akun tiktok",
                    "- Harap memasukkan password dan klik tombol login"
                ]
                show_notification("\n".join(messages))
                for message in messages:
                    self._process.log(message)
                self._process.log("- Silahkan resume untuk melanjutkan proses")

                def is_resume():
                    return not driver.is_element_exist(password_selector)
                self._process.wait_user_response_or_wait_until(
                    callback_to_resume=is_resume)
                close_notification()
                self._process.log("Melanjutkan proses selanjutnya")

            # check login response
            login_respose_selectors = [
                is_login_selector,
                '#captcha-verify-container-main-page, #idv-web-root',
                '[type="error"] > [role="status"]',
            ]
            (i_login_response, el_login_response) = driver.wait_elements_exist(
                login_respose_selectors, 15)

            if i_login_response == -1:
                self._logger.error(f"Login {self.name} Trigger Error![2]")

                messages = [
                    "Login trigger error",
                    "- Silahkan melanjutkan proses login secara manual"
                ]
                show_notification("\n".join(messages))
                for message in messages:
                    self._process.log(message)
                self._process.log("- Silahkan resume untuk melanjutkan proses")
                def is_resume(): return driver.is_element_exist(
                    login_respose_selectors[0])
                self._process.wait_user_response_or_wait_until(
                    callback_to_resume=is_resume)
                close_notification()
                self._process.log("Melanjutkan proses selanjutnya")

            if i_login_response == 1:
                messages = [
                    "Membutuhkan verifikasi tiktok",
                    "- Harap menyelesaikan verifikasi",
                ]
                show_notification("\n".join(messages))
                for message in messages:
                    self._process.log(message)
                self._process.log("- Silahkan resume untuk melanjutkan proses")
                self._process.wait_user_response_or_wait_until(
                    callback_to_resume=is_success_login)
                close_notification()
                self._process.log("Melanjutkan proses selanjutnya")

            (i_login_response, el_login_response) = driver.wait_elements_exist(
                login_respose_selectors, 15)

            if i_login_response == 0:
                self._process.log("Success: Login berhasil.", 'success')
                self._process.log("Menyimpan auto login.")
                self.save_driver_cookies()
                return True
            elif i_login_response == 1:
                self._process.log(
                    "Gagal login: Belum menyelesaikan verifikasi", 'failed')
            elif i_login_response == 2:
                self._process.log(
                    f"Gagal Login: {el_login_response.text.strip()}", 'failed')
                self._logger.error(
                    f"Gagal Login: {el_login_response.text.strip()}")
            else:
                self._process.log("Gagal login: Login trigger error", 'failed')
                self._logger.error(f"Login {self.name} Trigger Error![3]")

        except Exception as e:
            self._process.log(
                f"Gagal memproses Login {self.label.title()}!", 'failed')
            self._logger.error(
                f"Gagal memproses Login {self.name}:"
                f"{e}\n---\n{traceback.format_exc()}\n---"
            )

        # save cookie meskipun gagal
        # mengamankan success login tapi trigger error
        self.save_driver_cookies()
        return False

    def load_driver(self, **kwargs):
        """
        Load driver (membuat var driver jika belum ada)
        beserta Clear & Set Cookies dr username yang ditentukan.
        ```
        kwargs = {
            username: ...
            target_url: ...
            driver_params: ...
        }
        ```
        """
        if kwargs.get('username'):
            self._username = kwargs.get('username')
        has_driver = self._has_driver()
        driver = self._get_driver(kwargs.get('driver_params', {}))

        if not has_driver:
            # NOTE: jika sebelumnya tidak ada browser, maka dianggap cookie masih bersih.  # noqa
            self._logger.debug(
                "Doesn't Have Driver (New Chrome)."
                "Naigate ke `base_url`: %s" % self.base_url
            )
            driver.get(self.base_url)
            try:
                driver.switch_to_alert().accept()
            except:  # noqa
                pass
        else:
            # NOTE: Jika chrome sudah ada & tingal berpindah profile,
            # maka hapus dulu cookies yang sudah ada pada browser.
            self._logger.debug(
                "Has Driver. Naigate ke `base_url`: %s" % self.base_url)

            # STEP: Pastikan bahwa driver sedang membuka Domain yang akan di beri Cookies  # noqa
            if not driver.current_url.startswith(self.base_url):
                driver.get(self.base_url)
                try:
                    driver.switch_to_alert().accept()
                except:  # noqa
                    pass

        self._logger.debug("RESET Preious Cookies")
        driver.delete_all_cookies()
        driver.command_executor._commands['SEND_COMMAND'] = (
            'POST', '/session/$sessionId/chromium/send_command')
        driver.execute('SEND_COMMAND', dict(
            cmd='Network.clearBrowserCookies', params={}))
        driver.execute_cdp_cmd("Storage.clearDataForOrigin", {
            "origin": "https://seller-id.tokopedia.com/",
            "storageTypes": "all"
        })
        driver.execute_cdp_cmd("Storage.clearDataForOrigin", {
            "origin": "https://www.tiktok.com/",
            "storageTypes": "all"
        })
        driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})

        self._logger.debug("SET ulang Cookies dari cookie yang tersimpan")
        # self.load_driver_cookie()
        if self.has_cookie_file():
            if self.valid_account(self._username):
                self.load_driver_cookie()
            else:
                driver.delete_all_cookies()
                driver.command_executor._commands['SEND_COMMAND'] = (
                    'POST', '/session/$sessionId/chromium/send_command')
                driver.execute('SEND_COMMAND', dict(
                    cmd='Network.clearBrowserCookies', params={}))
                driver.get(self.base_url)
                try:
                    driver.switch_to_alert().accept()
                except:  # noqa
                    pass
        driver.get(kwargs.get('target_url', self.base_url))
        try:
            driver.switch_to_alert().accept()
        except:  # noqa
            pass

    def login(self, username: str, password: str, **kwargs):
        self._username = username
        self._process.log(f"Memulai auto login {self.label}...")

        login_data = self.is_logged_in(username, **kwargs)
        self._process.log(login_data.get('message'))

        if login_data.get('status') == LoginStatus.IS_LOGGED_IN:
            return True
        self.close_session()
        return self.do_login(username, password, **kwargs)
