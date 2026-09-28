import os
import shutil
import re
import sys
import json
import logging
import threading
import requests
import zipfile
import traceback
import random
import time
from pyquery import PyQuery
from typing import Optional
import calendar
from datetime import datetime, timedelta
# import struct
import subprocess
import uuid

import qlobot_api
from qlobot.configs import APPDATA_PATH
from .gservices.tiktok_main import TiktokMain, LoginStatus
from .database import setup_database, AccountModel, ProjectModel, VideoModel
from .chrome import Chrome, ChromeOptions

logger = logging.getLogger(__name__)


_PACKAGES_PATH = os.path.join(APPDATA_PATH, 'Launcher', 'packages')
_PACKAGE_LIST = {
    'ffmpeg': {
        'type': 'exe',
        'version': '2024-02-04-git-7375a6ca7b-full',
        'download_url': 'https://dl.dropboxusercontent.com/scl/fi/ugj3vs5bxwr3r6p4xymqj/ffmpeg.zip?rlkey=maciomuckiu9sgas25rcv9g5m&st=0no5sleh&dl=0',  # noqa
    },
    'pychrome': {
        'type': 'package',  # package | exe
        'version': '0.2.4',
        'download_url': 'https://docs.google.com/uc?export=download&id=1U5JjdFUClhIWdzaYEg-OPJ_fmImgazFo',
    },
}


class PackageInstaller:
    @staticmethod
    def is_installed(package: str):
        package_path = os.path.join(_PACKAGES_PATH, package)
        if _PACKAGE_LIST[package].get('type') == 'exe':
            return os.path.isfile(os.path.join(package_path, f'{package}.exe'))
        if _PACKAGE_LIST[package].get('type') == 'package':
            return os.path.isdir(
                os.path.join(
                    package_path,
                    f"{package}-{_PACKAGE_LIST[package].get('version')}"
                    ".dist-info"
                )
            )

    @staticmethod
    def load(package: str):
        package_path = os.path.join(_PACKAGES_PATH, package)
        if _PACKAGE_LIST[package].get('type') == 'exe':
            os.environ['PATH'] += os.pathsep + package_path
        if _PACKAGE_LIST[package].get('type') == 'package':
            sys.path.append(package_path)

    @staticmethod
    def download(package: str):
        if not os.path.isdir(_PACKAGES_PATH):
            os.makedirs(_PACKAGES_PATH)

        package_zip_path = os.path.join(_PACKAGES_PATH, package+'.zip')
        success_download = False
        package_download_url = _PACKAGE_LIST[package].get('download_url')

        for i in range(1, 4):
            if i > 1:
                print(f"- Memuat ulang {i} ...")
            try:
                with open(package_zip_path, "wb") as f:
                    # print("- Downloading %s" % chromium_zip_path)
                    print("- Downloading package ...")
                    response = requests.get(package_download_url, stream=True)
                    total_length = response.headers.get('content-length')

                    if total_length is None:  # no content length header
                        f.write(response.content)
                    else:
                        dl = 0
                        total_length = int(total_length)
                        for data in response.iter_content(chunk_size=4096):
                            dl += len(data)
                            f.write(data)
                            progres = dl / total_length
                            done = int(50 * progres)
                            sys.stdout.write("\r[%s%s] %s%% " % (
                                '=' * done, ' ' * (50-done),
                                str(round(100 * progres, 2)))
                            )
                            sys.stdout.flush()
                print('')
                success_download = True
            except Exception as e:
                logger.error(
                    "Error download package: "
                    f"{e}\n-----\n{traceback.format_exc()}\n-----"
                )
            if success_download:
                break

        if success_download:
            print("- Ekstrak package ...")
            success_download = False
            for i in range(1, 4):
                if i > 1:
                    print(f"- Ekstrak package {i} ...")
                try:
                    with zipfile.ZipFile(package_zip_path, 'r') as zipObj:
                        zipObj.extractall(_PACKAGES_PATH)
                    success_download = True
                except Exception as e:
                    logger.error(
                        "Error ekstrak package: "
                        f"{e}\n-----\n{traceback.format_exc()}\n-----"
                    )
                if success_download:
                    break

        for i in range(1, 4):
            if not os.path.exists(package_zip_path):
                break
            try:
                os.remove(package_zip_path)
            except:  # noqa
                pass

        if success_download:
            print("- Success")
            return True

        print("- Failed")
        return False


def install_packages():
    qlobot_api.GlobalVars.video_crafter_package_installed = []
    try:
        packages_to_install = []
        for package in _PACKAGE_LIST.keys():
            if PackageInstaller.is_installed(package):
                PackageInstaller.load(package)
                qlobot_api.GlobalVars.video_crafter_package_installed.append(
                    package)
                continue
            packages_to_install.append(package)

        packages_to_install_count = len(packages_to_install)
        if not packages_to_install:
            qlobot_api.GlobalVars.installing_video_crafter = False
            return

        print('\n# Install Packages')
        for (install_no, package) in enumerate(packages_to_install, start=1):
            print(
                "Download package "
                f"{install_no}/{packages_to_install_count} ..."
            )
            PackageInstaller.download(package)
            PackageInstaller.load(package)
            qlobot_api.GlobalVars.video_crafter_package_installed.append(
                package)
    except Exception as e:
        logger.error(
            "Error installing package: "
            f"{e}\n-----\n{traceback.format_exc()}\n-----"
        )
    qlobot_api.GlobalVars.installing_video_crafter = False


if not hasattr(qlobot_api.GlobalVars, "uploader_video_tiktok_init"):
    qlobot_api.GlobalVars.uploader_video_tiktok_init = True
    try:
        setup_database()
    except Exception as e:
        logger.error(
            f"Error install database: {e}\n---\n{traceback.format_exc()}\n---"
        )
    thread = threading.Thread(target=install_packages)
    thread.start()


def get_current_time(time_format=r"%Y%m%d%H%M%S"):
    return qlobot_api.helpers.current_datetime(time_format)

# -------------------------------------------------------------------------
# Process
# -------------------------------------------------------------------------


class UploadVideoProcess(qlobot_api.ProcessItem):
    name = "Upload Video Tiktok"
    dev_env = False

    main_url = "https://www.tiktok.com/"
    upload_url = 'https://www.tiktok.com/tiktokstudio/upload?from=webapp'
    upload_file_selector = 'input[type="file"][accept="video/*"]'

    driver = None
    chrome = None
    user_data_dir = ''

    video_status = {}

    def _get_chrome(self):
        if self.chrome is None:
            user_data_dir = f"profile--{self.tool_id}-{self._id}"
            self.user_data_dir = os.path.join(qlobot_api.TEMP_PATH, user_data_dir)
            options = ChromeOptions()
            options.start_url = self.main_url
            options.user_data_dir = self.user_data_dir
            options.port = 9240 + int(self._id)
            self.chrome = Chrome(options)
            self.chrome.network_enable()
        return self.chrome

    def _sleep(self, a=2, b=9):
        time.sleep(random.randint(a, b) / 10)

    def _get_latest_video(self):
        url_videos = 'https://www.tiktok.com/tiktok/creator/manage/item_list/v1/'  # noqa
        res_videos = self.autologin.post_request(
            url=url_videos,
            json={
                "cursor": 0,
                "size": 50,
                "query": {
                    "sort_orders": [{"field_name": "post_time", "order": 2}],
                    "conditions": [],
                    "is_recent_posts": False,
                }
            },
        )
        print('res_videos', res_videos)
        print('res_videos_data', res_videos.json())
        res_videos_data = res_videos.json()
        list_video = res_videos_data.get('item_list', [])
        return list_video[0] if list_video else {}

    def _mark_status(self, video, status, adt_data={}):
        self.video_status[video['id']] = status
        payload = {
            'id': video['id'],
            'upload_status': status,
            **adt_data,
        }
        VideoModel.update(payload)
        self.ws_broadcast('edit_videos', [payload])

    # stage upload

    def _stage_login(self, video):
        account = video['account']
        try:
            account['password'] = qlobot_api.decrypt(account['password'])
        except Exception:
            pass

        is_login = self.autologin.login(account['username'], account['password'])
        if not is_login:
            raise qlobot_api.ProcessExecption('Gagal login')

        self._close_driver()
        return account

    def _stage_prepare_upload_page(self):
        self.log('Buka Halaman Upload')

        chrome = self._get_chrome()
        chrome.clear_data()
        chrome.load_cookies(self.autologin._get_cookie_identity_name())

        chrome.navigate(self.upload_url)
        chrome.wait_loading(timeout=15)
        self._sleep()

        if not chrome.wait_element_exist(self.upload_file_selector, 15):
            raise qlobot_api.ProcessExecption('Halaman upload gagal dimuat')
        self._sleep()

        self.log('- Finish')

    def _stage_upload_file(self, video):
        self.log('Upload file video')

        chrome = self._get_chrome()
        chrome.execute_script_void(
            f"var el = document.querySelector(`{self.upload_file_selector}`);"
            "if (el) {"
            " el.removeAttribute('hidden');"
            " el.style.visibility = 'visible';"
            " el.style.display = 'block';"
            "}"
        )
        abs_video_path = os.path.abspath(video['video_path'])
        if not chrome.upload_file(self.upload_file_selector, abs_video_path):
            raise qlobot_api.ProcessExecption('Gagal upload video')

        upload_done_selector = '[data-e2e="upload_status_container"] .info-status.success'
        upload_modal_close_selector = '.common-modal .common-modal-close-icon'
        for _ in range(0, 5):
            i_uploaded = chrome.wait_elements_exist([
                upload_done_selector,  # noqa
                upload_modal_close_selector,
            ], 5)
            if i_uploaded == 0:
                break
            if i_uploaded == 1:
                chrome.click_element(upload_modal_close_selector)
                self._sleep()

        self.log('- Finish')
        return True

    def _stage_input_caption(self, video):
        self.log('Input Caption')

        chrome = self._get_chrome()

        # close modal
        if chrome.is_element_exist('.common-modal .common-modal-close-icon'):
            chrome.click_element('.common-modal .common-modal-close-icon')
            self._sleep()

        # close tutorial
        for _ in range(0, 3):
            if chrome.is_element_exist('.tutorial-tooltip button'):
                chrome.click_element('.tutorial-tooltip button')
                self._sleep()
            else:
                break

        caption_selector = '.caption-editor [contenteditable]'
        chrome.scroll_into_view(caption_selector)
        time.sleep(random.randint(2, 5)/10)
        chrome.set_contenteditable_text(
            caption_selector, video.get('caption') or '')
        self._sleep()

        self.log('- Finish')

    def _stage_input_showcase(self, account, video):
        if not (account['meta']['affiliate'] and video['showcase']):
            return

        self.log('Input Showcase')

        chrome = self._get_chrome()

        for showcase in video['showcase']:
            self.log(f'- Add showcase: {showcase["product_title"]}')

            add_product_selector = '[data-e2e="anchor_container"] button'
            chrome.click_element(add_product_selector)
            time.sleep(random.randint(9, 19)/10)

            chrome.wait_element_exist('.anchor-modal', 5)
            # common-modal-width--compact

            add_product_selector = '.TUXSelect-button'
            chrome.click_element(add_product_selector)
            time.sleep(random.randint(9, 19)/10)

            add_product_selector = '.TUXSelect-menuOption'
            chrome.click_element(add_product_selector)
            time.sleep(random.randint(9, 19)/10)

            add_product_selector = '.anchor-modal [class$="--primary"]'
            chrome.click_element(add_product_selector)
            time.sleep(random.randint(9, 19)/10)

            container_selector = '.product-selector-modal'
            chrome.wait_element_exist(container_selector, 5)

            chrome.execute_script_void("document.querySelector('.product-selector-modal')?.classList.remove('common-modal-width--compact');")  # noqa
            time.sleep(random.randint(2, 5)/10)

            close_selector = '.common-modal-footer [class$="--secondary"]'
            chrome.wait_element_exist(close_selector, 5)
            search_selector = container_selector + \
                ' .product-search-input input[type="text"]'
            chrome.wait_element_exist(search_selector, 5)
            search_found = chrome.is_element_exist(search_selector)
            if not search_found:
                showcase_tab_selector = '.product-search-bar button[id="2"]'  # noqa
                if chrome.is_element_exist(showcase_tab_selector):
                    chrome.click_element(showcase_tab_selector)
                    time.sleep(random.randint(9, 19)/10)
                    chrome.wait_element_exist(search_selector, 5)
                    search_found = chrome.is_element_exist(search_selector)
            if not search_found:
                self.log('- Skip add showcase: product tidak ditemukan atau tidak aktif')  # noqa
                chrome.click_element(close_selector)
                time.sleep(random.randint(2, 9)/10)
                continue
            chrome.fill_input(search_selector, showcase['product_id'])
            time.sleep(random.randint(2, 5)/10)
            chrome.press_enter()
            time.sleep(random.randint(9, 19)/10)

            product_select_selector = container_selector + \
                ' .product-table input[type="radio"]:not([disabled])'
            chrome.wait_element_exist(product_select_selector, 5)

            if not chrome.is_element_exist(product_select_selector):
                self.log('- Skip add showcase: product tidak ditemukan atau tidak aktif')  # noqa
                chrome.click_element(close_selector)
                time.sleep(random.randint(2, 9)/10)
                continue

            chrome.click_element(product_select_selector)
            time.sleep(random.randint(9, 19)/10)

            chrome.wait_element_exist(close_selector, 5)
            submit_selector = '.common-modal-footer [class$="--primary"]:not([disabled])'  # noqa
            if not chrome.is_element_exist(submit_selector):
                self.log('- Skip add showcase: product tidak ditemukan atau tidak aktif.')  # noqa
                chrome.click_element(close_selector)
                time.sleep(random.randint(2, 9)/10)
                continue

            chrome.click_element(submit_selector)
            time.sleep(random.randint(9, 19)/10)

            chrome.wait_element_exist(close_selector, 5)
            submit_selector = '.common-modal-footer [class$="--primary"]:not([disabled])'  # noqa
            if not chrome.is_element_exist(submit_selector):
                self.log('- Skip add showcase: product tidak ditemukan atau tidak aktif..')  # noqa
                chrome.click_element(close_selector)
                time.sleep(random.randint(2, 9)/10)
                continue

            chrome.click_element(submit_selector)
            time.sleep(random.randint(9, 19)/10)
            self.log('- Success')

        self.log('- Finish')

    def _stage_input_settings(self, video, params):
        self.log('Input Settings')

        chrome = self._get_chrome()

        schedule = video.get('schedule')
        if schedule:
            self.log('- Set Schedule')
            dt = datetime.fromisoformat(schedule.replace("Z", "+00:00")).astimezone()
            # print('dt', dt)
            # pembulatan 5 menit
            discard = timedelta(minutes=dt.minute % 5, seconds=dt.second, microseconds=dt.microsecond)
            dt -= discard
            if discard >= timedelta(minutes=2.5):
                dt += timedelta(minutes=5)
            # print('dt', dt)

            current_dt = datetime.now(dt.tzinfo)

            year = current_dt.year + (current_dt.month // 12)
            month = current_dt.month % 12 + 1
            day = min(current_dt.day, calendar.monthrange(year, month)[1])
            max_dt = current_dt.replace(year=year, month=month, day=day)

            if dt > (current_dt) + timedelta(minutes=15) and dt < max_dt:
                schedule_selector = '[data-e2e="schedule_container"]'
                chrome.scroll_into_view(schedule_selector)
                time.sleep(random.randint(2, 9)/10)
                schedule_selector = 'label:has([name="postSchedule"]):nth-child(2)'  # noqa
                chrome.click_element(schedule_selector)
                time.sleep(random.randint(2, 9)/10)

                input_selector = '.scheduled-picker>div:nth-child(1) input'
                chrome.click_element(input_selector)
                time.sleep(random.randint(2, 9)/10)

                h = dt.hour + 1
                # print('h', h)
                input_selector = f'.tiktok-timepicker-time-picker-container>div:nth-child(2) .tiktok-timepicker-option-item:nth-child({h}) .tiktok-timepicker-option-text'  # noqa
                # print('sel', input_selector)
                chrome.execute_script_void(
                    "document.querySelector(`" + input_selector + "`)?.click();"  # noqa
                )
                time.sleep(random.randint(2, 9)/10)

                m = int(dt.minute / 5) + 1
                # print('m', m)
                input_selector = f'.tiktok-timepicker-time-picker-container>div:nth-child(3) .tiktok-timepicker-option-item:nth-child({m}) .tiktok-timepicker-option-text'  # noqa
                # print('sel', input_selector)
                chrome.execute_script_void(
                    "document.querySelector(`" + input_selector + "`)?.click();"  # noqa
                )
                time.sleep(random.randint(2, 9)/10)

                input_selector = '.scheduled-picker>div:nth-child(2) input'
                chrome.click_element(input_selector)
                time.sleep(random.randint(2, 9)/10)

                chrome.scroll_into_view('.calendar-wrapper')
                diff_month = (dt.year - current_dt.year) * 12 + (dt.month - current_dt.month)  # noqa
                # print('diff_month', diff_month)
                for _ in range(diff_month):
                    # print('click next')
                    chrome.execute_script_void(
                        "document.querySelector('.month-header-wrapper .arrow:last-child')?.click();"  # noqa
                    )
                    time.sleep(random.randint(2, 9)/10)

                d = dt.day
                # print('d', d)
                chrome.execute_script_void(f"Array.from(document.querySelectorAll('.day.valid')).filter(el => el.textContent == '{d}').forEach(el => el.click())")  # noqa
                time.sleep(random.randint(2, 9)/10)
            else:
                self.log('Skip schadule: invalid date schadule')

        visibility = params.get('visibility').replace('_', ' ')
        visibility_selector = '[data-e2e="video_visibility_container"] button'
        visibility_text = chrome.get_text(visibility_selector).strip().lower()
        if visibility_text != visibility:
            self.log('- Set visibility')
            chrome.click_element(visibility_selector)
            time.sleep(random.randint(2, 9)/10)
            opt_selector = '.Select__content [role="option"]:nth-child(3)'
            if visibility == 'everyone':
                opt_selector = '.Select__content [role="option"]:nth-child(1)'
            if visibility == 'friends':
                opt_selector = '.Select__content [role="option"]:nth-child(2)'
            chrome.click_element(opt_selector)
            time.sleep(random.randint(2, 9)/10)

        show_more_selector = '[data-e2e="advanced_settings_container"]'
        chrome.click_element(show_more_selector)
        time.sleep(random.randint(2, 9)/10)

        # allow comment
        user_perm_selector = '[data-e2e="user_perm_container"] '
        allow_comment_selector = user_perm_selector + \
            '.checkbox:nth-child(1) input[type="checkbox"]'
        allow_comment = (
            chrome.get_attribute(allow_comment_selector, "checked")
        ) is not None
        if params.get('allow_comment') != allow_comment:
            self.log('- Set allow comment')
            allow_comment_selector = user_perm_selector + '.checkbox:nth-child(1) label'
            chrome.scroll_into_view(allow_comment_selector)
            chrome.click_element(allow_comment_selector)
            time.sleep(random.randint(2, 9)/10)

        # allow reuse

        allow_reuse_selector = user_perm_selector + \
            '.checkbox:nth-child(2) input[type="checkbox"]'
        allow_reuse = (
            chrome.get_attribute(allow_reuse_selector, "checked")
        ) is not None
        if params.get('allow_reuse') != allow_reuse:
            self.log('- Set allow reuse')
            allow_reuse_selector = user_perm_selector + '.checkbox:nth-child(2) label'
            chrome.scroll_into_view(allow_reuse_selector)
            chrome.click_element(allow_reuse_selector)
            time.sleep(random.randint(2, 9)/10)

        disclose_content_selector = '[data-e2e="disclose_content_container"]'
        disclose_content = (
            chrome.get_attribute(
                disclose_content_selector + ' .Switch__root .Switch__content',
                "data-state"
            )
        ) == 'checked'
        if (
            params.get('disclose_content')
            and not params.get('your_brand')
            and not params.get('branded_content')
        ):
            params['disclose_content'] = False

        if params.get('disclose_content') != disclose_content:
            self.log('- Set disclose content')
            disclose_content_selector += ' .Switch__root input'
            chrome.scroll_into_view(disclose_content_selector)
            chrome.click_element(disclose_content_selector)
            time.sleep(random.randint(2, 9)/10)
            has_checked = False
            if params.get('disclose_content'):
                brands_selector = '.options-form > div:not([data-e2e]) '
                if params.get('your_brand'):
                    brand_selector = brands_selector + '.text-container:nth-child(1) label'
                    chrome.click_element(brand_selector)
                    is_checked = chrome.get_attribute(brand_selector, "data-checked") == 'true'
                    if is_checked:
                        has_checked = True
                if params.get('branded_content'):
                    brand_selector = brands_selector + '.text-container:nth-child(2) label'
                    chrome.click_element(brand_selector)
                    is_checked = chrome.get_attribute(brand_selector, "data-checked") == 'true'
                    if is_checked:
                        has_checked = True
            if not has_checked:
                chrome.click_element(disclose_content_selector)
                time.sleep(random.randint(2, 9)/10)

        aigc_selector = '[data-e2e="aigc_container"]'
        aigc = (
            chrome.get_attribute(
                aigc_selector + ' .Switch__root .Switch__content',
                "data-state"
            )
        ) == 'checked'
        if params.get('aigc') != aigc:
            self.log('- Set aigc')
            aigc_selector += ' .Switch__root input'
            chrome.scroll_into_view(aigc_selector)
            chrome.click_element(aigc_selector)
            time.sleep(random.randint(2, 9)/10)
            if params.get('aigc') and chrome.is_element_exist('.common-modal'):
                chrome.click_element(
                    '.common-modal button[data-type="primary"]'
                )
                time.sleep(random.randint(2, 9)/10)

        self.log('- Finish')

    def _stage_input_check(self, params):
        self.log('Input Check')

        chrome = self._get_chrome()

        copyright_selector = '[data-e2e="copyright_container"]'
        copyright = (
            chrome.get_attribute(
                copyright_selector + ' .Switch__root .Switch__content',
                "data-state"
            )
        ) == 'checked'
        if params.get('copyright') != copyright:
            self.log('- Set copyright')
            copyright_selector += ' .Switch__root'
            chrome.scroll_into_view(copyright_selector)
            chrome.click_element(copyright_selector + ' input')
            time.sleep(random.randint(2, 9)/10)

        content_check_selector = '.card:last-child > div > div:last-child [data-layout="switch-root"]:last-child'  # noqa
        content_check = (
            chrome.get_attribute(
                content_check_selector + ' .Switch__content',
                "data-state"
            )
        ) == 'checked'
        if params.get('content_check') != content_check:
            self.log('- Set content check')
            chrome.scroll_into_view(content_check_selector)
            chrome.click_element(content_check_selector + ' input')
            time.sleep(random.randint(2, 9)/10)

        self.log('- Finish')

    def _stage_publish(self):
        self.log('Click Publish')

        chrome = self._get_chrome()

        def click_publish():
            button_posting_selector = '[data-e2e="post_video_button"]'
            chrome.scroll_into_view(button_posting_selector)
            chrome.click_element(button_posting_selector)
            button_posting_selector = '.common-modal .TUXButton--primary'
            if chrome.wait_element_exist(button_posting_selector, 5):
                chrome.click_element(button_posting_selector)

        video_data = chrome.capture_network_action(click_publish, ["/project/post/v1"], 30)

        if video_data:
            single_post_resp_list = video_data.get('single_post_resp_list', [])
            if single_post_resp_list:
                return single_post_resp_list[0].get('item_id')

            logger.error(f"Failed upload, res: {json.dumps(video_data)}")
            raise qlobot_api.ProcessExecption(video_data.get("status_msg", "Unknow"))
        return False

    # upload orchestration

    def do_upload_video(self, video, params):
        self._mark_status(video, 'uploading')

        account = self._stage_login(video)
        video['account']['account_username'] = account['account_username']

        self._stage_prepare_upload_page()
        self._stage_upload_file(video)
        self._stage_input_caption(video)
        self._stage_input_showcase(account, video)
        self._stage_input_settings(video, params)
        self._stage_input_check(params)
        # self.wait_user_response()
        return self._stage_publish()

    # process

    def on_execute(self, videos, params):
        if self.dev_env:
            os.system('cls' if os.name == 'nt' else 'clear')
            self.log('Forward log to cmd')
            os.system('cls' if os.name == 'nt' else 'clear')

        # print('params', json.dumps(params, indent=4))
        self.log(f"Starting {self.name!r}")
        # print('videos, params', videos, params)

        # setup report
        videos_len = len(videos)
        self.reports['success'] = 0
        self.reports['failed'] = 0
        self.reports['target'] = videos_len
        self.reports['status'] = "Waiting"

        # update status waiting
        bc_data = []
        for video in videos:
            self.video_status[video['id']] = 'waiting'
            bc_data.append({
                'id': video['id'],
                'upload_status': 'waiting',
            })
            VideoModel.update(bc_data[-1])
        self.ws_broadcast('edit_videos', bc_data)

        params['delay_start'] = params.get('delay_start', 20)
        params['delay_end'] = params.get('delay_end', 30)

        self.autologin = TiktokMain(self)

        for _i, video in enumerate(videos):
            self.reports['status'] = f"Uploading {_i + 1}"
            self.log(f"#{_i + 1} upload video, username: {video['account']['username']}")

            try:
                video_id = self.do_upload_video(video, params)
                if video_id:
                    video_url = (
                        "https://www.tiktok.com/"
                        f"@{video['account']['account_username']}/video/{video_id}"
                    )
                    self.reports['success'] += 1
                    self._mark_status(video, 'uploaded', {
                        'uploaded_at': get_current_time()
                    })
                    self.log(f'Success Upload, video url: {video_url}')
                else:
                    self.reports['failed'] += 1
                    self._mark_status(video, 'failed')
                    self.log('Failed Upload: Unknow')
            except qlobot_api.ProcessExecption as e:
                self.reports['failed'] += 1
                self._mark_status(video, 'failed')
                self.log(f'Failed Upload: {e}')
            except Exception as e:
                self.reports['failed'] += 1
                self._mark_status(video, 'failed')
                self.log('Failed Upload: Terjadi kesalahan')
                logger.error(f"Error upload video: {e}\n---\n{traceback.format_exc()}\n---")
                if self.dev_env:
                    self.log(f"Error upload video: {e}\n---\n{traceback.format_exc()}\n---")

            delay = random.randint(params['delay_start'], params['delay_end'])
            if videos_len < _i + 1:
                self.log('Delaying {} seconds'.format(str(delay)))
                for _ in range(0, delay):
                    time.sleep(1)

        self.reports['status'] = "Finish"

    def stop(self):
        for video_id, status in self.video_status.items():
            if status in ['failed', 'uploaded']:
                continue
            self._mark_status({'id': video_id}, 'cancel')

        super().stop()

    def _close_driver(self):
        if not self.driver:
            return
        try:
            self.driver.close()
        except Exception:
            pass
        self.driver = None

    def _close_chrome(self):
        if not self.chrome:
            return
        try:
            self.chrome.close()
        except Exception:
            pass
        self.chrome = None

        for _ in range(0, 20):
            if not self.user_data_dir or not os.path.exists(self.user_data_dir):
                break
            try:
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
            except Exception:
                pass

    def on_stoped(self):
        self.log("Process stoped.")
        self.reports['status'] = "Stoped"
        self._close_driver()
        self._close_chrome()

    def on_execute_except(self, exc):
        self._close_driver()
        self._close_chrome()
        self.log(f"Gagal {self.name}")
        logger.error(f"Gagal {self.name}:{exc}\n---\n{exc.exc_info}\n---")
        if self.dev_env:
            self.log(f"Gagal {self.name}:{exc}\n---\n{exc.exc_info}\n---")

    def on_execute_finish(self):
        self._close_driver()
        self._close_chrome()
        self.log("Process has finish.")
        self.log(
            f"Reports: {self.reports['success']} Success, {self.reports['failed']} Failed"
        )


class AccountChecker:
    @classmethod
    def _get_showcase(cls, service, page, try_count: int = 0):
        try:
            url_get_showcase = (
                'https://shop.tiktok.com/api/v1'
                '/streamer_desktop/showcase_product/list'
            )
            params_get_showcase = {
                'offset': page * 6,
                'count': 6,
            }
            res_get_showcase = service.get_request(
                url=url_get_showcase,
                params=params_get_showcase,
            )
            # print('res_get_showcase', res_get_showcase)
            # print('res_get_showcase_data', res_get_showcase.json())
            return res_get_showcase.json()
        except requests.exceptions.JSONDecodeError as e:
            raise e
        except Exception as e:
            if try_count >= 0:
                raise e
            time.sleep(random.randint(2, 9)/10)
            return cls._get_showcase(service, page, try_count + 1)

    @classmethod
    def check(
        cls, account, driver: Optional[qlobot_api.InjectorBrowser] = None
    ):
        result = {
            'loggenin': account['loggenin'],
            'account_name': account['account_name'],
            'account_username': account['account_username'],
            'account_picture': account['account_picture'],
            'last_check_at': get_current_time(),
            'meta': account['meta'],
        }
        service = TiktokMain(logger=logger)

        login_data = service.is_logged_in(account['username'])
        result["loggenin"] = login_data.get('status')
        if result["loggenin"] is not LoginStatus.IS_LOGGED_IN:
            result['meta']['last_error'] = login_data.get('message')
            if service is not None:
                service.close_session()

            return result

        user_data = login_data.get('data', {})
        # print('user_data', json.dumps(user_data, indent=4))

        result['account_username'] = user_data.get('username')
        if not result['account_name']:
            result['account_name'] = user_data.get('screen_name')
        if not result['account_picture']:
            result['account_picture'] = user_data.get('avatar_url')

        # get account detail with browser

        if driver is not None:
            try:
                html_content_text = driver.execute_async_script(f"""
                    const done = arguments[arguments.length - 1];
                    fetch('{service.base_url}')
                        .then(r => r.text())
                        .then(text => done(text));
                """)
                html_content_dom = PyQuery(html_content_text)
                script_data = html_content_dom(
                    '#__UNIVERSAL_DATA_FOR_REHYDRATION__'
                ).text()
                # print('script_data', script_data)
                script_parsed_data = json.loads(script_data)
                script_user_data = (
                    script_parsed_data
                    .get('__DEFAULT_SCOPE__', {})
                    .get('webapp.app-context', {})
                    .get('user', {})
                )

                if script_user_data.get('nickName'):
                    result['account_name'] = script_user_data.get('nickName')

                avatarUri = script_user_data.get('avatarUri')
                if (
                    avatarUri
                    and type(avatarUri) is list
                    and type(avatarUri[-1]) is str
                ):
                    result['account_picture'] = avatarUri[-1]

            except Exception as e:
                logger.error(
                    f"Error get profile: {e}"
                    f"\n---\n{traceback.format_exc()}\n---"
                )

        # gets product showcase

        try:
            result['showcase'] = []

            def add_product_var(products):
                for product in products:
                    thumb = product.get('cover', {})
                    images = product.get('images', [])
                    if not thumb and images:
                        thumb = images[0]
                    thumbs_url = thumb.get('url_list', [])
                    str_price = product.get('format_available_price', '0')
                    price = int(re.sub(r'\D', '', str_price))
                    can_added = product.get('can_added', False)

                    result['showcase'].append({
                        'product_id': product.get('product_id'),
                        'product_url': "https://shop-id.tokopedia.com/pdp/p/" + product.get('product_id', ''),  # noqa
                        'product_title': product.get('title'),
                        'product_thumb': thumbs_url[0] if thumbs_url else '',
                        'product_price': price,
                        'product_stock': product.get('stock_num', 0),
                        'product_commission': (
                            product.get('affiliate_info', {})
                            .get('commission_expense', 0)
                        ),
                        'product_can_added': 1 if can_added else 0,
                    })

            res_showcase = cls._get_showcase(service, 0)
            if res_showcase.get('message', '') == 'success':
                result['meta']['affiliate'] = True

                add_product_var(
                    res_showcase.get('data', {}).get('products', [])
                )

                if res_showcase.get('data', {}).get('total', 0) > 6:
                    total = res_showcase.get('data', {}).get('total', 0)
                    paginate_next = int(total / 6) + \
                        (1 if total % 6 > 0 else 0)

                    for i in range(1, paginate_next):
                        res_showcase_next = cls._get_showcase(service, i)
                        if res_showcase_next.get('message', '') == 'success':
                            add_product_var(
                                res_showcase_next
                                .get('data', {}).get('products', [])
                            )

            elif 'no permission' in res_showcase.get('message', ''):
                result['meta']['affiliate'] = False

        except Exception as identifier:
            logger.error(
                f"Request Parse Error: {identifier}"
                f"\n-----\n{traceback.format_exc()}\n-----"
            )

        if service is not None:
            service.close_session()

        return result


class AutoLoginProccess(qlobot_api.ProcessItem):
    name = "Auto Login Tiktok"
    dev_env = False

    driver = None

    def _close_driver(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def on_execute(self, params):
        if self.dev_env:
            os.system('cls' if os.name == 'nt' else 'clear')
            self.log("> Forward log to cmd")
            os.system('cls' if os.name == 'nt' else 'clear')
        # print('params', json.dumps(params, indent=4))
        self.log(f"Starting {self.name!r}")

        accounts = AccountModel.gets_where_in('id', params['ids'])
        if not accounts:
            self.log("Tidak ada account ditemukan untuk proses Auto Login.")
            return

        self.log("Persiapan Auto Login: %s Account" % len(accounts))
        self.reports['success'] = 0
        self.reports['failed'] = 0

        service = TiktokMain(self)

        for i, account in enumerate(accounts):
            # check_result = AccountChecker.check(account)
            # print('check_result', json.dumps(check_result, indent=4))
            # continue

            # self.log(account)
            self.log(f"#{i + 1} Memproses Login {account['username']}")
            try:
                account['password'] = qlobot_api.decrypt(account['password'])
            except:  # noqa
                pass

            account_data = {
                'id': account['id'],
                'loggenin': 0,
            }

            success_login = service.do_login(
                account['username'], account['password'])
            if success_login:
                self.reports['success'] += 1

                check_result = AccountChecker.check(
                    account, driver=self.driver
                )
                # print('check_result', json.dumps(check_result, indent=4))

                account_data = {
                    **account_data,
                    **check_result,
                }
                # print('account_data', json.dumps(account_data, indent=4))
            else:
                self.reports['failed'] += 1

            AccountModel.update(account_data)
            self.ws_broadcast(
                'edit_accounts', [AccountModel.get_by_id(account['id'])]
            )

    def on_execute_except(self, exc):
        self._close_driver()
        self.log(f"Gagal {self.name}")
        logger.error(f"Gagal {self.name}:{exc}\n---\n{exc.exc_info}\n---")
        if self.dev_env:
            self.log(f"Gagal {self.name}:{exc}\n---\n{exc.exc_info}\n---")

    def on_execute_finish(self):
        self._close_driver()
        self.reports = {**{'success': 0, 'failed': 0}, **self.reports}
        finish_message = "Proses Auto Login telah selesai."
        reports_message = (
            "Reports: "
            f"{self.reports['success']} Success, "
            f"{self.reports['failed']} Failed"
        )
        self.log(finish_message)
        self.log(reports_message)


# -------------------------------------------------------------------------
# Web Handlers crudy
# -------------------------------------------------------------------------


class ActionHandler(qlobot_api.ToolActionHandler):
    default_action: str = 'main'

    def setup(self):
        pass

    def run(self):
        req_url = self.webhandler.request.uri.split('?')[0]
        paths = [_ for _ in req_url.split('/') if _]
        action = self.default_action if len(paths) <= 5 else paths[5]
        action_name = 'action_' + action
        if not hasattr(self, action_name):
            return self.webhandler.json_output({
                "success": False,
                'message': 'Invalid action'
            })

        self.setup()
        return getattr(self, action_name)()


class AccountHandler(ActionHandler):
    default_action: str = 'gets'

    def action_gets(self):
        return self.webhandler.json_output({
            "success": True,
            'data': AccountModel.gets()
        })

    def action_gets_dict_with_products(self):
        return self.webhandler.json_output({
            "success": True,
            'data': AccountModel.gets_dict_with_products()
        })

    def action_create(self):
        params = self.webhandler.json_body()
        if not params.get('name', '').strip():
            return self.webhandler.json_output({
                "success": False,
                "message": "Nama harus diisi."
            })
        if not params.get('username', '').strip():
            return self.webhandler.json_output({
                "success": False,
                "message": "Username/Email harus diisi."
            })

        payload = {
            'name': params.get('name', '').strip(),
            'username': params.get('username', '').strip(),
        }
        password = params.get('password', '')
        if password:
            payload['password'] = qlobot_api.encrypt(password)
        insert_id = AccountModel.insert(payload)

        self.ws_broadcast('add_accounts', [AccountModel.get_by_id(insert_id)])

        return self.webhandler.json_output({
            "success": True,
        })

    def action_update(self):
        params = self.webhandler.json_body()
        account = AccountModel.get_by_id(params.get('id'))
        if not account:
            return self.webhandler.json_output({
                "success": False,
                "message": "Account tidak ditemukan."
            })
        if not params.get('name', '').strip():
            return self.webhandler.json_output({
                "success": False,
                "message": "Nama harus diisi."
            })
        if not params.get('username', '').strip():
            return self.webhandler.json_output({
                "success": False,
                "message": "Username/Email harus diisi."
            })

        payload = {
            "id": params['id'],
            "name": params['name'].strip(),
            "username": params['username'].strip(),
        }
        password = params.get('Password', '')
        if password:
            payload['Password'] = qlobot_api.encrypt(password)

        AccountModel.update(payload)
        self.ws_broadcast(
            'edit_accounts', [AccountModel.get_by_id(params['id'])]
        )

        return self.webhandler.json_output({
            "success": True,
        })

    def action_delete(self):
        params = self.webhandler.json_body()
        if not params.get('ids') or type(params.get('ids')) != list:
            return self.webhandler.json_output({
                "success": False,
                "message": "Invalid args."
            })

        AccountModel.bulk_delete_by_id(params['ids'])
        self.ws_broadcast('delete_accounts', params['ids'])

        return self.webhandler.json_output({
            "success": True,
        })

    def action_autologin(self):
        params = self.webhandler.json_body()
        if not params.get('ids') or type(params.get('ids')) != list:
            return self.webhandler.json_output({
                "success": False,
                "message": "Invalid args."
            })

        process = AutoLoginProccess()
        process.execute_args = (params, )
        process.dev_env = not self.tool._compiled
        process.print_log = not self.tool._compiled
        process.execute()

        return self.webhandler.json_output({
            "success": True,
        })

    def action_refresh(self):
        params = self.webhandler.json_body()
        if not params.get('ids') or type(params.get('ids')) != list:
            return self.webhandler.json_output({
                "success": False,
                "message": "Invalid args."
            })
        accounts = AccountModel.gets_where_in('id', params.get('ids'))
        if not accounts:
            return self.webhandler.json_output({
                "success": False,
                "message": "Tidak ada account ditemukan."
            })

        service = TiktokMain()
        for account in accounts:
            is_logged_in = service.is_logged_in(username=account['username'])

            account_data = {
                'id': account['id'],
                'loggenin': 0,
            }

            if is_logged_in.get('status') == 1:
                check_result = AccountChecker.check(account)
                account_data = {
                    **account,
                    **check_result,
                }
                # print('account_data', json.dumps(account_data, indent=4))

            AccountModel.update(account_data)
            self.ws_broadcast(
                'edit_accounts', [AccountModel.get_by_id(account['id'])]
            )

        return self.webhandler.json_output({
            "success": True,
        })


class ProjectHandler(ActionHandler):
    default_action: str = 'gets'

    def action_gets(self):
        projects = ProjectModel.gets_last_update()
        if len(projects) == 0:
            ProjectModel.insert({
                'name': 'Untitled Project #1',
            })
            projects = ProjectModel.gets_last_update()
        return self.webhandler.json_output({
            "success": True,
            'data': projects
        })

    def action_create(self):
        project_no = 0
        projects = ProjectModel.gets()
        for project in projects:
            if len(project['name'].split('#')) < 2:
                continue
            try:
                temp_no = int(project['name'].split('#')[-1])
                if temp_no > project_no:
                    project_no = temp_no
            except:  # noqa
                pass
        insert_id = ProjectModel.insert({
            'name': f'Untitled Project #{project_no + 1}',
        })

        return self.webhandler.json_output({
            "success": True,
            "data": ProjectModel.get_by_id(insert_id),
        })

    def action_update(self):
        params = self.webhandler.json_body()
        project = ProjectModel.get_by_id(params.get('id'))
        if not project:
            return self.webhandler.json_output({
                "success": False,
                "message": "Project tidak ditemukan."
            })

        ProjectModel.update({**project, **params})

        return self.webhandler.json_output({
            "success": True,
            "data": ProjectModel.get_by_id(params['id']),
        })

    def action_delete(self):
        params = self.webhandler.json_body()
        if not params.get('id'):
            return self.webhandler.json_output({
                "success": False,
                "message": "Invalid args."
            })

        ProjectModel.delete_by_id(params['id'])

        return self.webhandler.json_output({
            "success": True,
        })


class VideoHandler(ActionHandler):
    default_action: str = 'gets'

    project: dict = {}

    def run(self):
        req_url = self.webhandler.request.uri.split('?')[0]
        paths = [_ for _ in req_url.split('/') if _]
        project_id = paths[5]
        self.project = ProjectModel.get_by_id(project_id)
        if not self.project:
            return self.webhandler.json_output({
                "success": False,
                'message': 'Tidak menemukan project'
            })
        action = self.default_action if len(paths) <= 6 else paths[6]
        action_name = 'action_' + action
        if not hasattr(self, action_name):
            return self.webhandler.json_output({
                "success": False,
                'message': 'Invalid action'
            })

        return getattr(self, action_name)()

    def action_gets(self):
        return self.webhandler.json_output({
            "success": True,
            'data': VideoModel.gets_project(self.project.get('id'))
        })

    def action_add_folder(self):
        params = self.webhandler.json_body()
        if not params.get('folder_path'):
            return self.webhandler.json_output({
                "success": False,
                'message': 'Invalid param'
            })
        folder_path = params.get('folder_path')
        if not os.path.isdir(folder_path):
            return self.webhandler.json_output({
                "success": False,
                'message': 'Folder tidak ditemukan'
            })

        project_videos = VideoModel.gets_where(
            'project_id', self.project.get('id')
        )
        project_videos_path = [_['video_path'] for _ in project_videos]
        videos_path = []
        for filename in os.listdir(folder_path):
            video_path = os.path.join(folder_path, filename)
            if (
                not filename.endswith('mp4')
                or video_path in project_videos_path
            ):
                continue
            videos_path.append(video_path)

        videos_id = []
        for video_path in videos_path:
            videos_id.append(VideoModel.insert({
                'project_id': self.project.get('id'),
                'video_path': video_path,
            }))

        if videos_id:
            self.ws_broadcast(
                'add_videos', VideoModel.gets_where_in('id', videos_id)
            )

        return self.webhandler.json_output({
            "success": True,
            "data": {
                'video_count': len(videos_id)
            },
        })

    def action_update(self):
        params = self.webhandler.json_body()
        # print('params', json.dumps(params, indent=4))
        video = VideoModel.get_by_id(params.get('id'))
        if not video:
            return self.webhandler.json_output({
                "success": False,
                "message": "Video tidak ditemukan."
            })

        if params.get('showcase_ids'):
            VideoModel.update_showcase(params)
        else:
            udate_data = {**video, **params}
            if not udate_data['schedule']:
                udate_data['schedule'] = ''
            VideoModel.update(udate_data)
        self.ws_broadcast(
            'edit_videos', [VideoModel.get_by_id(params.get('id'))]
        )

        return self.webhandler.json_output({
            "success": True,
        })

    def action_bulk_update(self):
        params = self.webhandler.json_body()
        if type(params.get('ids')) is not list or not params.get('ids') or not params.get('data'):
            return self.webhandler.json_output({
                "success": False,
                "message": "Invalid args."
            })

        update_data = params.get('data')
        videos = VideoModel.gets_ids(params.get('ids'))
        if update_data.get('showcase_ids'):
            for video in videos:
                VideoModel.update_showcase({'id': video['id'], **update_data})
        else:
            for video in videos:
                VideoModel.update({'id': video['id'], **update_data})

        videos = VideoModel.gets_ids(params.get('ids'))
        self.ws_broadcast('edit_videos', videos)

        return self.webhandler.json_output({
            "success": True,
        })

    def action_delete(self):
        params = self.webhandler.json_body()
        if not params.get('ids') and type(params.get('ids')) is not list:
            return self.webhandler.json_output({
                "success": False,
                "message": "Invalid args."
            })

        VideoModel.bulk_delete_by_id(params['ids'])
        self.ws_broadcast('delete_videos', params['ids'])

        return self.webhandler.json_output({
            "success": True,
        })


class BrowseFolderHandler(qlobot_api.ToolActionHandler):
    def run(self):
        ps_script = r'''
        Add-Type -AssemblyName System.Windows.Forms

        # Buat dummy form sebagai parent agar dialog selalu di depan
        $owner = New-Object System.Windows.Forms.Form
        $owner.TopMost = $true
        $owner.StartPosition = 'CenterScreen'
        $owner.Size = New-Object System.Drawing.Size(0, 0)
        $owner.Show()
        $owner.Activate()

        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.ValidateNames = $false
        $dialog.CheckFileExists = $false
        $dialog.CheckPathExists = $true
        $dialog.FileName = "Select Folder"

        $result = $dialog.ShowDialog($owner)

        $owner.Dispose()

        if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
            Split-Path $dialog.FileName
        }
        '''
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                ps_script
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        folder_path = result.stdout.strip()
        if folder_path:
            return self.webhandler.json_output({
                "success": True,
                "folder_path": folder_path,
            })
        self.webhandler.json_output({
            "success": False,
        })


class PreviewVideoHandler(qlobot_api.ToolActionHandler):
    def run(self):
        path = self.webhandler.get_argument("path", '')
        self.webhandler.set_header("Content-Type", "video/mp4")
        self.webhandler.set_header("Cache-Control", "public, max-age=86400")
        with open(path, "rb") as f:
            self.webhandler.write(f.read())


class PreviewVideoThumbHandler(qlobot_api.ToolActionHandler):
    def run(self):
        path = self.webhandler.get_argument("path", '')
        key = self.webhandler.get_argument("key", '')
        temp_name = f"tmp_cover_video.{key if key else str(uuid.uuid4())}.jpg"
        temp_path = os.path.join(qlobot_api.TEMP_PATH, temp_name)

        self.webhandler.set_header("Content-Type", "image/jpeg")
        self.webhandler.set_header("Cache-Control", "public, max-age=86400")

        if os.path.isfile(temp_path):
            with open(temp_path, "rb") as f:
                self.webhandler.write(f.read())
            return

        subprocess.run([
            "ffmpeg.exe", "-i", path, "-ss", "00:00:00", "-vframes", "1",
            "-y", temp_path
        ], capture_output=True)
        with open(temp_path, "rb") as f:
            self.webhandler.write(f.read())
        if not key:
            os.unlink(temp_path)


# -------------------------------------------------------------------------
# Web Handlers
# -------------------------------------------------------------------------


class UploadVideoHandler(qlobot_api.ToolActionHandler):
    def run(self):
        default_params = {
            "project_id": 0,
            "data_upload": "count_per_account",
            "count_per_account": 1,
            "checked_video_ids": [],
            "visibility": "everyone",
            "allow_comment": True,
            "allow_reuse": True,
            "disclose_content": False,
            "your_brand": False,
            "branded_content": False,
            "aigc": False,
            "copyright": False,
            "content_check": False,
            "delay_start": 20,
            "delay_end": 30,
        }
        params = self.webhandler.json_body()
        data_upload_options = ['count_per_account', 'checked_video']
        params = {**default_params, **params}

        # validate param

        if params.get('data_upload') not in data_upload_options:
            return self.webhandler.json_output({
                "success": False,
                "message": 'Pilih data untuk diupload',
            })

        if (
            params['data_upload'] == 'count_per_account'
            and (
                type(params.get('count_per_account')) is not int
                or params.get('count_per_account') < 1
            )
        ):
            return self.webhandler.json_output({
                "success": False,
                "message": 'Jumlah video per akun minimal 1',
            })

        if (
            params['data_upload'] == 'checked_video'
            and (
                type(params.get('checked_video_ids')) is not list
                or not params.get('checked_video_ids')
            )
        ):
            return self.webhandler.json_output({
                "success": False,
                "message": 'Pilih video untuk diupload',
            })

        project = ProjectModel.get_by_id(params['project_id'])
        # print('project', json.dumps(project, indent=4))
        if not project:
            return self.webhandler.json_output({
                "success": False,
                "message": 'Project tidak ditemukan',
            })
        videos = VideoModel.gets_project(params['project_id'], True)
        if not videos:
            return self.webhandler.json_output({
                "success": False,
                "message": 'Tidak ada video untuk di upload atau akun belum ditambahkan ke video',  # noqa
            })
        # print('videos', json.dumps(videos, indent=4))

        video_to_upload = []
        if params['data_upload'] == 'checked_video':
            for video in videos:
                if video['id'] in params.get('checked_video_ids'):
                    video_to_upload.append(video)
        else:
            count_per_account = 1
            try:
                count_per_account = params.get('count_per_account', 1)
            except:  # noqa
                pass
            user_video = {}
            for video in videos:
                account_id = video['account_id']
                if account_id not in user_video:
                    user_video[account_id] = 0
                if user_video[account_id] >= count_per_account:
                    continue
                video_to_upload.append(video)
                user_video[account_id] += 1
        # print('video_to_upload', json.dumps(video_to_upload, indent=4), len(video_to_upload))  # noqa
        if not video_to_upload:
            return self.webhandler.json_output({
                "success": False,
                "message": 'Tidak ada video untuk di upload atau akun belum ditambahkan ke video.',  # noqa
            })

        # params['videos'] = video_to_upload
        # print('params', json.dumps(params, indent=4))

        process = UploadVideoProcess()
        process.description = f'Upload {len(video_to_upload)} videos'
        process.execute_args = (video_to_upload, params, )
        process.dev_env = not self.tool._compiled
        process.print_log = not self.tool._compiled
        process.execute()

        self.webhandler.json_output({
            "success": True,
        })


TOOL_ACTIONS = {
    r'/run': UploadVideoHandler,
    r"/account/?([0-9a-zA-Z_]+)?": AccountHandler,
    r"/project/?([0-9a-zA-Z_]+)?": ProjectHandler,
    r"/video/([0-9]+)/?([0-9a-zA-Z_]+)?": VideoHandler,
    r'/browse_folder': BrowseFolderHandler,
    r'/preview_video': PreviewVideoHandler,
    r'/preview_video_thumb': PreviewVideoThumbHandler,
}
