import os
import sys
import socket
import subprocess
import atexit
from typing import List
import logging
# import traceback
import time
# import random
import json
import requests  # type: ignore

from qlobot.configs import APPDATA_PATH, CHREME_BINARY, COOKIES_STORAGE_PATH
from qlobot.core.pcookies import PCookies

import warnings
warnings.filterwarnings("ignore", message=".*Network.getResponseBody error.*")

used_ports = []


class ChromeOptions:
    port: int = 0
    start_url: str = None
    user_data_dir: str = None
    args: List[str] = []
    close_atexit: bool = False


class Chrome():
    _process: subprocess.Popen = None
    _logger: logging.Logger = None

    options: ChromeOptions = ChromeOptions()
    _browser = None
    _capture_tab = None
    _network_filters = []  # type: List[str]
    _network_request_ids = []  # type: List[str]
    _network_enabled = False
    default_args = [
        # disable restore
        # Disable "Chrome didn't shut down correctly"
        "--disable-session-crashed-bubble",
        "--no-first-run",                        # Skip first run wizard
        "--no-default-browser-check",            # Skip default browser check
        "--disable-default-apps",                # Disable default apps
        "--disable-restore-session-state",       # Disable session restore
        "--disable-background-mode",             # Disable background mode

        # disable notifications
        "--disable-notifications",               # Disable all notifications
        "--disable-desktop-notifications",       # Disable desktop notifications
        "--disable-push-messaging",              # Disable push messaging
        "--disable-permission-action-reporting",  # Disable permission reporting

        # disable location
        "--disable-geolocation",                 # Disable geolocation
        "--disable-features=Geolocation",        # Disable geolocation feature

        # disable translate
        "--disable-translate",
        "--disable-features=Translate",
        "--disable-features=TranslateUI",        # Disable translate

        # disable remember password
        "--disable-password-manager-reauthentication",  # Disable password manager reauth
        "--disable-save-password-bubble",        # Disable save password bubble
        "--password-store=basic",                # Use basic password store
        "--disable-features=PasswordManager",    # Disable password manager feature

        # additional privacy & security flags
        # "--disable-web-security",                # Disable web security (optional)
        "--disable-ipc-flooding-protection",     # Disable IPC flooding protection
        "--disable-renderer-backgrounding",      # Disable renderer backgrounding
        # Disable backgrounding occluded windows
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",  # Disable background timer throttling
        "--disable-features=MediaRouter",        # Disable cast
        # Disable component extensions
        "--disable-component-extensions-with-background-pages",

        # debugging & automation
        # "--no-sandbox",                          # Disable sandbox (untuk automation)
        "--disable-dev-shm-usage",               # Disable /dev/shm usage
        # Disable GPU (optional, untuk headless)
        "--disable-gpu",
        "--disable-software-rasterizer",

        "--disable-background-networking",
        "--disable-sync",
        "--disable-extensions",
        "--disable-popup-blocking",
        "--disable-client-side-phishing-detection",
        "--disable-hang-monitor",
        "--disable-prompt-on-repost",
    ]

    def __init__(self, options: ChromeOptions = None, logger: logging.Logger = None):
        if options is not None:
            self.options = options
        if not self.options.port:
            self.options.port = self.get_free_port()
        used_ports.append(self.options.port)

        self._logger = logger
        if self._logger is None:
            self._logger = logging.getLogger(__name__)

        # state per instance (jangan pakai mutable class attribute)
        self._capture_tab = None
        self._network_filters = []
        self._network_request_ids = []
        self._network_enabled = False

    def get_free_port(self, counter=0):
        if counter > 15:
            raise Exception("Cannot get free port")
        free_port = 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            free_port = s.getsockname()[1]
        if free_port in used_ports:
            return self.get_free_port(counter + 1)
        if free_port > 0:
            return free_port
        return self.get_free_port(counter + 1)

    #
    # process
    #

    def launch(self):
        # print('launch')
        chrome_path = r'"C:\Program Files\Google\Chrome\Application\chrome.exe"'
        if CHREME_BINARY:
            chrome_path = CHREME_BINARY

        command = [chrome_path]
        if self.options.start_url:
            command.append(f'"{self.options.start_url}"')
        if self.options.user_data_dir:
            command.append(f'--user-data-dir="{self.options.user_data_dir}"')

        command.append(f'--remote-debugging-port={self.options.port}')

        # print('command::', command)
        command += self.default_args + self.options.args
        command = " ".join(command)
        # self._logger.info('open chrome command::' + command)
        self._process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if self.options.close_atexit:
            atexit.register(self.close)

        self.wait_port_open(timeout=5)

    def wait_port_open(self, timeout=15):
        for _ in range(0, timeout*2):
            if self.is_port_open():
                break
            time.sleep(0.5)

    def close(self):
        # print('close')
        try:
            self.stop_network_capture()
        except Exception:
            pass
        self._capture_tab = None
        if self._process:
            try:
                # self._browser.close()
                self.close_all_tab()
                # self._process.send_signal(signal.SIGTERM)
            except Exception:
                # print('error ', e, traceback.format_exc())
                pass
            self._process = None
        self._browser = None

    def is_port_open(self):
        try:
            endpoint_url = f"http://localhost:{self.options.port}/json/version"
            res = requests.get(endpoint_url, timeout=1)
            if res.status_code == 200:
                return True
        except Exception:
            return False

    def is_running(self):
        return self._process is not None and self._process.poll() is None

    #
    # browser
    #

    def get_browser(self):
        if not self.is_running() and not self.is_port_open():
            self._browser = None
            self.launch()
        if self._browser is None:
            remote_url = f"http://localhost:{self.options.port}"

            package_path = os.path.join(
                APPDATA_PATH, 'Launcher/packages/pychrome')
            sys.path.append(package_path)

            import pychrome  # type: ignore

            self._browser = pychrome.Browser(url=remote_url)
        return self._browser

    def get_tab(self, close_other_tabs=False):
        browser = self.get_browser()
        tabs = browser.list_tab()
        if close_other_tabs:
            for i in range(1, len(tabs)):
                browser.close_tab(tabs[i])
        if len(tabs) == 0:
            tab = browser.new_tab()
        else:
            tab = tabs[0]
        tab.start()
        return tab

    def activate_first_tab(self):
        browser = self.get_browser()
        tabs = browser.list_tab()
        if len(tabs) > 1:
            browser.activate_tab(tabs[0], timeout=3)
            tabs[0].start()

    def close_all_tab(self):
        if not self.is_running():
            return
        try:
            tabs = self._browser.list_tab()
            for tab in tabs:
                tab._stopped.set()
                self._browser.close_tab(tab)
        except Exception:
            # print('error ', e, traceback.format_exc())
            pass

    # navigate

    def navigate(self, url: str, timeout=15):
        try:
            self.get_tab().Page.navigate(url=url, _timeout=timeout)
        except Exception:
            pass

    def get_current_url(self):
        try:
            result = self.get_tab().Runtime.evaluate(
                expression="window.location.href")
        except Exception:
            return ''
        if not result:
            return ''
        value = result.get('result', {}).get('value')
        return value if value else ''

    def reload(self, ignoreCache=True):
        tab = self.get_tab()
        tab.Page.reload(ignoreCache=ignoreCache)

    # cookies

    def get_cookie(self, name: str):
        tab = self.get_tab()
        cookies = tab.Network.getAllCookies()["cookies"]
        target = next((c for c in cookies if c["name"] == name), None)
        return target["value"] if target else None

    def clear_data(self, origins=[]):
        tab = self.get_tab()
        tab.Network.clearBrowserCookies()
        tab.Network.clearBrowserCache()
        for origin in origins:
            tab.Storage.clearDataForOrigin(origin=origin, storageTypes="all")

    def get_cookie_path(self, identity_name: str):
        cookie_file = f"{identity_name}.qlobot-cookies"
        return os.path.join(COOKIES_STORAGE_PATH, cookie_file)

    def save_cookies(self, identity_name: str):
        tab = self.get_tab()
        cookies = tab.Network.getAllCookies().get('cookies', [])
        for cookie in cookies:
            if cookie.get('sameSite') == 'unspecified':
                del cookie['sameSite']
        cookie_path = self.get_cookie_path(identity_name)
        PCookies.save_cookies(cookie_path, cookies)

    def load_cookies(self, identity_name: str):
        tab = self.get_tab()
        cookie_path = self.get_cookie_path(identity_name)
        if not os.path.exists(cookie_path):
            return

        cookies = []
        try:
            cookies = PCookies.read_cookies(cookie_path)
        except Exception as e:
            self._logger.error(
                f'Cookie storage "{identity_name}" invalid format!')
            self._logger.error(e, exc_info=True)

        for cookie in cookies:
            if cookie.get('sameSite') == 'unspecified':
                del cookie['sameSite']
            cookie_args = dict(
                (k, v) for k, v in cookie.items() if k in (
                    'name', 'value', 'domain', 'path', 'secure',
                    'httpOnly', 'expires', 'sameSite',
                )
            )
            try:
                tab.Network.setCookie(**cookie_args)
            except Exception as e:
                self._logger.warning('Set cookie error: %s' % e)

    def set_cookies_from_list(self, cookies):
        """Set cookies dari list dict ala selenium (handoff login).

        Dipakai karena login tetap via Selenium (`TiktokMain`), sedangkan
        upload berjalan di instance Chrome pychrome yang terpisah.
        """
        if not cookies:
            return
        tab = self.get_tab()
        try:
            tab.Network.enable()
        except Exception:
            pass
        for cookie in cookies:
            try:
                cookie_args = {}
                if cookie.get('name'):
                    cookie_args['name'] = cookie.get('name')
                if cookie.get('value') is not None:
                    cookie_args['value'] = cookie.get('value')
                if cookie.get('domain'):
                    cookie_args['domain'] = cookie.get('domain')
                cookie_args['path'] = cookie.get('path', '/')
                if cookie.get('secure') is not None:
                    cookie_args['secure'] = bool(cookie.get('secure'))
                http_only = cookie.get('httpOnly', cookie.get('http_only'))
                if http_only is not None:
                    cookie_args['httpOnly'] = bool(http_only)
                expiry = cookie.get('expires', cookie.get('expiry'))
                if isinstance(expiry, (int, float)):
                    cookie_args['expires'] = int(expiry)
                same_site = cookie.get('sameSite', cookie.get('same_site'))
                if same_site and same_site != 'unspecified':
                    normalized = str(same_site).lower()
                    if normalized in ('no_restriction', 'none'):
                        cookie_args['sameSite'] = 'None'
                    elif normalized == 'lax':
                        cookie_args['sameSite'] = 'Lax'
                    elif normalized == 'strict':
                        cookie_args['sameSite'] = 'Strict'
                tab.Network.setCookie(**cookie_args)
            except Exception as e:
                self._logger.warning('Set cookie error: %s' % e)

    # element

    def is_element_exist(self, selector: str):
        try:
            tab = self.get_tab()
            if ':contains:' in selector:
                selector_arr = selector.split(':contains:')
                expression = f"""Array.from(document.querySelectorAll(`{selector_arr[0]}`)).filter(el => el.textContent.includes(`{selector_arr[-1]}`)).length > 0"""  # noqa
                result = tab.Runtime.evaluate(expression=expression)
                return True if result.get('result').get('value') else False
            expression = f"""document.querySelector(`{selector}`) !== null"""
            result = tab.Runtime.evaluate(expression=expression)
            return True if result.get('result').get('value') else False
        except Exception:
            return False

    def is_elements_exist(self, selectors: List[str]):
        for i in range(0, len(selectors)):
            if self.is_element_exist(selectors[i]):
                return i
        return -1

    def wait_element_exist(self, selector: str, timeout=30):
        for i in range(0, timeout*2):
            if self.is_element_exist(selector):
                return True
            time.sleep(0.5)
        return False

    def wait_elements_exist(self, selectors: List[str], timeout=30):
        for _i in range(0, timeout*2):
            el_index = self.is_elements_exist(selectors)
            if el_index >= 0:
                return el_index
            time.sleep(0.5)
        return -1

    def fill_input(self, selector: str, value):
        tab = self.get_tab()
        text = '' if value is None else str(value)
        tab.Runtime.evaluate(
            expression=f"""document.querySelector(`{selector}`).focus()""")
        # tab.Runtime.evaluate(expression=f"""document.querySelector(`{selector}`).select()""")
        event_payload = {
            'modifiers': 2,  # Ctrl
            'windowsVirtualKeyCode': 65,  # A
            'code': 'KeyA',
            'key': 'a'
        }
        tab.Input.dispatchKeyEvent(type="keyDown", **event_payload)
        tab.Input.dispatchKeyEvent(type="keyUp", **event_payload)
        tab.Input.insertText(text=text)

    def click_element(self, selector: str):
        tab = self.get_tab()
        event = 'new MouseEvent("click", { bubbles: true, cancelable: true })'
        expression = f"""document.querySelector(`{selector}`).dispatchEvent({event})"""
        tab.Runtime.evaluate(expression=expression)

    def press_enter(self):
        tab = self.get_tab()
        event_payload = {
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13,
            "key": "Enter",
            "code": "Enter",
        }
        tab.Input.dispatchKeyEvent(type="keyDown", **event_payload)
        tab.Input.dispatchKeyEvent(type="keyUp", **event_payload)

    def get_text_element(self, selector: str):
        tab = self.get_tab()
        expression = f"""document.querySelector(`{selector}`).textContent"""
        result = tab.Runtime.evaluate(expression=expression)
        return result['result']['value']

    def execute_script(self, script: str, **kwarg):
        try:
            tab = self.get_tab()
            result = tab.Runtime.evaluate(expression=script, **kwarg)
        except Exception:
            return None
        if not result:
            return None
        return result.get('result').get('value')

    def execute_script_void(self, script: str):
        tab = self.get_tab()
        tab.Runtime.evaluate(expression=script)

    def scroll_into_view(self, selector: str):
        tab = self.get_tab()
        expression = (
            "var el = document.querySelector(`" + selector + "`);"
            "if (el) { el.scrollIntoView(); }"
        )
        try:
            tab.Runtime.evaluate(expression=expression)
        except Exception:
            pass

    def get_attribute(self, selector: str, attr: str):
        tab = self.get_tab()
        expression = (
            "var el = document.querySelector(`" + selector + "`);"
            "el ? el.getAttribute(`" + attr + "`) : null"
        )
        try:
            result = tab.Runtime.evaluate(expression=expression)
        except Exception:
            return None
        if not result:
            return None
        return result.get('result', {}).get('value')

    def get_text(self, selector: str):
        tab = self.get_tab()
        expression = (
            "var el = document.querySelector(`" + selector + "`);"
            "el ? el.textContent : ''"
        )
        try:
            result = tab.Runtime.evaluate(expression=expression)
        except Exception:
            return ''
        value = result.get('result', {}).get('value')
        return value if value is not None else ''

    def select_all(self):
        tab = self.get_tab()
        event_payload = {
            'modifiers': 2,  # Ctrl
            'windowsVirtualKeyCode': 65,  # A
            'code': 'KeyA',
            'key': 'a'
        }
        tab.Input.dispatchKeyEvent(type="keyDown", **event_payload)
        tab.Input.dispatchKeyEvent(type="keyUp", **event_payload)

    def press_delete(self):
        tab = self.get_tab()
        event_payload = {
            "windowsVirtualKeyCode": 46,
            "nativeVirtualKeyCode": 46,
            "key": "Delete",
            "code": "Delete",
        }
        tab.Input.dispatchKeyEvent(type="keyDown", **event_payload)
        tab.Input.dispatchKeyEvent(type="keyUp", **event_payload)

    def set_contenteditable_text(self, selector: str, text):
        """Isi elemen contenteditable (caption TikTok).

        Fokus + Ctrl+A + insertText (mengganti seleksi) + dispatch event
        `input` agar editor framework (React) mendeteksi perubahan.
        """
        tab = self.get_tab()
        text = '' if text is None else str(text)
        self.scroll_into_view(selector)
        tab.Runtime.evaluate(
            expression="document.querySelector(`" + selector + "`).focus()")
        self.select_all()
        try:
            self.press_delete()
        except Exception:
            pass
        tab.Runtime.evaluate(
            expression="document.querySelector(`" + selector + "`).focus()")
        tab.Input.insertText(text=text if text else ' ')
        tab.Runtime.evaluate(
            expression=(
                "var el = document.querySelector(`" + selector + "`);"
                "if (el) {"
                " el.dispatchEvent(new Event('input', {bubbles: true}));"
                " el.dispatchEvent(new Event('change', {bubbles: true}));"
                "}"
            ))

    def clear_input(self, selector: str):
        tab = self.get_tab()
        tab.Runtime.evaluate(
            expression="document.querySelector(`" + selector + "`).focus()")
        self.select_all()
        self.press_delete()

    def upload_file(self, selector: str, file_path: str):
        """Upload file via CDP DOM.setFileInputFiles (tanpa dialog OS).

        Returns True jika berhasil, False jika gagal.
        """
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            self._logger.error('File upload tidak ditemukan: %s' % abs_path)
            return False
        tab = self.get_tab()
        try:
            try:
                tab.DOM.enable()
            except Exception:
                pass
            doc = tab.DOM.getDocument(depth=0)
            root_id = doc.get('root', {}).get('nodeId', 0)
            if not root_id:
                return False
            res = tab.DOM.querySelector(nodeId=root_id, selector=selector)
            node_id = res.get('nodeId', 0)
            if not node_id:
                self._logger.error(
                    'Input upload tidak ditemukan: %s' % selector)
                return False
            tab.DOM.setFileInputFiles(files=[abs_path], nodeId=node_id)
            return True
        except Exception as e:
            self._logger.error('Gagal upload file: %s' % e, exc_info=True)
            return False

    def wait_loading(self, timeout=15):
        def is_complete():
            return self.execute_script('document.readyState == "complete"')
        for _ in range(0, timeout):
            if is_complete():
                break

    #
    # network capture
    #

    def network_enable(self):
        tab = self.get_tab()
        tab.Network.enable()

    def capture_network_action(self, action, endpoints, timeout=15, request_no=1):
        result = {
            'requestId': None,
            'data': None,
            'request_no': request_no,
        }
        tab = self.get_tab()

        # Optimasi 1: Kompilasi regex sekali di luar handler
        endpoint_patterns = [endpoint for endpoint in endpoints]

        def handle_response_received(**kwargs):
            # Optimasi 2: Early return jika sudah dapat data
            if result['data'] is not None:
                return
            response = kwargs.get("response", {})
            url = response.get("url", "")

            # Optimasi 3: Cek mime type dulu (lebih cepat)
            if response.get('mimeType') != 'application/json':
                return
            # Optimasi 4:Gunakan any() untuk short-circuit
            if not any(endpoint in url for endpoint in endpoint_patterns):
                return

            if result['request_no'] > 1:
                result['request_no'] -= 1
                return

            result['requestId'] = kwargs.get("requestId")

            # Optimasi 5: Langsung coba ambil body
            try:
                response_data = tab.Network.getResponseBody(
                    requestId=result['requestId'])
                result['data'] = json.loads(response_data.get('body'))
            except Exception:
                pass

        def on_loading_finished(**kwargs):
            # Optimasi 6: Early return lebih awal
            if result['data'] is not None or not result['requestId']:
                return
            if kwargs.get("requestId") != result['requestId']:
                return

            try:
                response_data = tab.Network.getResponseBody(
                    requestId=result['requestId'])
                result['data'] = json.loads(response_data.get('body'))
            except Exception:
                pass

        tab.Network.responseReceived = handle_response_received
        tab.Network.loadingFinished = on_loading_finished

        action()

        start = time.time()
        # Optimasi 7: Fixed - kondisi while yang benar & interval lebih besar
        while result['data'] is None and time.time() - start < timeout:
            tab.wait(0.25)  # Naikkan dari 0.01 ke 0.05 (kurangi CPU usage)

        # Optimasi 8: Cleanup listener
        tab.set_listener("Network.responseReceived", None)
        tab.set_listener("Network.loadingFinished", None)

        return result['data']

    #
    # magic
    #

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
