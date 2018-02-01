import pytest
import urllib2
import json
import re
import tempfile
import gzip
import time
import os

from os.path import abspath, realpath, dirname, join

from selenium.common.exceptions import NoSuchElementException

#import crypto_util
from step_helpers import screenshots, LOG_DIR


class JournalistNavigationStepsMixin():

    @screenshots
    def _get_submission_content(self, file_url, raw_content):
        if not file_url.endswith(".gz.gpg"):
            return str(raw_content)

        with tempfile.TemporaryFile() as fp:
            fp.write(raw_content.data)
            fp.seek(0)

            gzf = gzip.GzipFile(mode='rb', fileobj=fp)
            content = gzf.read()

            return content

    def return_downloaded_content(self, url, cookies):
        """
        This downloads and returns the content to the caller
        :param url: URL to download
        :param cookies: the cookies to access
        :return: Content of the URL
        """
        temp_cookie_file = tempfile.NamedTemporaryFile('w', delete=False)
        data = {'url': url, 'cookies': cookies}
        json.dump(data, temp_cookie_file)
        temp_cookie_file.close()

        cmd_path = abspath(join(dirname(realpath(__file__)), 'download_content.py'))
        # Now call the external program to handle the download
        cmd = 'python {0} {1}'.format(cmd_path, temp_cookie_file.name)
        if '.onion' in url:
            cmd = 'torify ' + cmd
        raw_content = self.system(cmd).strip()
        return raw_content

    def _input_text_in_login_form(self, username, password, token):
        self.driver.get(self.journalist_location + "/login")
        username_field = self.driver.find_element_by_css_selector(
            'input[name="username"]')
        username_field.send_keys(username)

        password_field = self.driver.find_element_by_css_selector(
            'input[name="password"]')
        password_field.send_keys(password)

        token_field = self.driver.find_element_by_css_selector(
            'input[name="token"]')
        token_field.send_keys(token)

    def _try_login_user(self, username, password, token):
        self._input_text_in_login_form(username, password, token)
        self.driver.get_screenshot_as_file(os.path.join(LOG_DIR, "journalist.png"))
        submit_button = self.driver.find_element_by_css_selector(
            'button[type="submit"]')
        submit_button.send_keys(u'\ue007')

    @screenshots
    def _login_user(self, username, password, token):
        self._try_login_user(username, password, token)
        # Successful login should redirect to the index
        self.driver.get_screenshot_as_file(os.path.join(LOG_DIR, "journalist2.png"))
        time.sleep(10)
        assert self.driver.current_url == self.journalist_location + '/', self.driver.current_url

    @screenshots
    def _journalist_logs_in(self):
        # Create a test user for logging in
        self.user, self.user_pw = self.admin_user['name'], self.admin_user['password']
        self._login_user(self.user, self.user_pw, str(self.admin_user['totp'].now()))

        headline = self.driver.find_element_by_css_selector('span.headline')
        if not hasattr(self, 'accept_languages'):
            assert 'Sources' in headline.text

    def _journalist_visits_col(self):
        self.driver.find_element_by_css_selector(
            '#un-starred-source-link-1').click()

    def _journalist_selects_first_doc(self):
        self.driver.find_elements_by_name('doc_names_selected')[0].click()

    def _journalist_clicks_delete_selected_javascript(self):
        self.driver.find_element_by_id('delete-selected').click()
        self._alert_wait()

    def _journalist_verifies_deletion_of_one_submission_javascript(self):
        self._journalist_selects_first_doc()
        self._journalist_clicks_delete_selected_javascript()
        self._alert_dismiss()
        time.sleep(5)
        selected_count = len(self.driver.find_elements_by_name(
            'doc_names_selected'))
        assert selected_count > 0
        self._journalist_clicks_delete_selected_javascript()
        self._alert_accept()
        time.sleep(5)
        assert selected_count > len(self.driver.find_elements_by_name(
            'doc_names_selected'))

    @screenshots
    def _admin_logs_in(self):
        self.admin, self.admin_pw = self.admin_user['name'], self.admin_user['password']
        self._login_user(self.admin, self.admin_pw, str(self.admin_user['totp'].now()))

        if not hasattr(self, 'accept_languages'):
            # Admin user should log in to the same interface as a
            # normal user, since there may be users who wish to be
            # both journalists and admins.
            headline = self.driver.find_element_by_css_selector(
                'span.headline')
            assert 'Sources' in headline.text

            # Admin user should have a link that take them to the admin page
            links = self.driver.find_elements_by_tag_name('a')
            assert 'Admin' in [el.text for el in links]

    @screenshots
    def _admin_visits_admin_interface(self):
        admin_interface_link = self.driver.find_element_by_id(
            'link-admin-index')
        admin_interface_link.click()
        time.sleep(self.sleep_time)
        if not hasattr(self, 'accept_languages'):
            h1s = self.driver.find_elements_by_tag_name('h1')
            assert "Admin Interface" in [el.text for el in h1s]

    def _admin_visits_system_config_page(self):
        system_config_link = self.driver.find_element_by_id(
            'update-instance-config'
        )
        system_config_link.click()
        time.sleep(self.sleep_time)
        if not hasattr(self, 'accept_languages'):
            h1 = self.driver.find_element_by_tag_name('h1')
            assert "Instance Configuration" in h1.text

    def _admin_updates_logo_image(self):
        image_path = os.path.abspath(os.path.join(os.path.dirname(LOG_DIR), 'static/i/logo.png'))
        logo_upload_input = self.driver.find_element_by_id('logo-upload')
        logo_upload_input.send_keys(image_path)


        submit_button = self.driver.find_element_by_id('submit-logo-update')
        submit_button.click()
        time.sleep(self.sleep_time)

        if not hasattr(self, 'accept_languages'):
            flashed_msgs = self.driver.find_element_by_css_selector('.flash')
            assert 'Image updated.' in flashed_msgs.text

    @screenshots
    def _add_user(self, username, is_admin=False, hotp=None):
        username_field = self.driver.find_element_by_css_selector(
            'input[name="username"]')
        username_field.send_keys(username)

        if hotp:
            hotp_checkbox = self.driver.find_element_by_css_selector(
                'input[name="is_hotp"]')
            print(str(hotp_checkbox.__dict__))
            hotp_checkbox.click()
            hotp_secret = self.driver.find_element_by_css_selector(
                'input[name="otp_secret"]')
            hotp_secret.send_keys(hotp)

        if is_admin:
            # TODO implement (checkbox is unchecked by default)
            pass

        submit_button = self.driver.find_element_by_css_selector(
            'button[type=submit]')
        submit_button.click()

    @screenshots
    def _admin_adds_a_user(self):
        add_user_btn = self.driver.find_element_by_css_selector(
            'button#add-user')
        add_user_btn.click()
        time.sleep(self.sleep_time)

        if not hasattr(self, 'accept_languages'):
            # The add user page has a form with an "ADD USER" button
            btns = self.driver.find_elements_by_tag_name('button')
            assert 'ADD USER' in [el.text for el in btns]

        password = self.driver.find_element_by_css_selector('#password') \
            .text.strip()

        self.new_user = dict(
                username='dellsberg',
                password=password,
            )
        self._add_user(self.new_user['username'])

        if not hasattr(self, 'accept_languages'):
            # Clicking submit on the add user form should redirect to
            # the FreeOTP page
            h1s = self.driver.find_elements_by_tag_name('h1')
            assert "Enable FreeOTP" in [el.text for el in h1s]


        shared_secret = self.driver.find_element_by_css_selector('#shared-secret') \
                        .text.strip().replace(' ', '')
        self.create_new_totp(shared_secret)

        # Verify the two-factor authentication
        token_field = self.driver.find_element_by_css_selector(
            'input[name="token"]')
        token_field.send_keys(str(self.new_totp.now()))
        submit_button = self.driver.find_element_by_css_selector(
            'button[type=submit]')
        submit_button.click()

        time.sleep(self.sleep_time)
        if not hasattr(self, 'accept_languages'):
            # Successfully verifying the code should redirect to the admin
            # interface, and flash a message indicating success
            flashed_msgs = self.driver.find_elements_by_css_selector('.flash')
            assert (("Token in two-factor authentication "
                     "accepted for user {}.").format(
                         self.new_user['username']) in
                    [el.text for el in flashed_msgs])

    def _admin_can_send_test_alert(self):
        alert_button = self.driver.find_element_by_id('test-ossec-alert')
        alert_button.click()

        if not hasattr(self, 'accept_languages'):
            flashed_msg = self.driver.find_element_by_css_selector('.flash')
            assert "Test alert sent. Check your email." in flashed_msg.text

    @screenshots
    def _logout(self):
        # Click the logout link
        logout_link = self.driver.find_element_by_id('link-logout')
        logout_link.click()

        # Logging out should redirect back to the login page
        def login_page():
            assert ("Login to access the journalist interface" in
                    self.driver.page_source)
        self.wait_for(login_page)

    @screenshots
    def _check_login_with_otp(self, otp):
        self._logout()
        self._login_user(self.new_user['username'],
                         self.new_user['password'], otp)
        if not hasattr(self, 'accept_languages'):
            # Test that the new user was logged in successfully
            assert 'Sources' in self.driver.page_source

    @screenshots
    def _new_user_can_log_in(self):
        # Log the admin user out
        self._logout()

        time.sleep(60)
        # Log the new user in
        self._login_user(self.new_user['username'],
                         self.new_user['password'],
                         str(self.new_totp.now()))

        if not hasattr(self, 'accept_languages'):
            # Test that the new user was logged in successfully
            assert 'Sources' in self.driver.page_source

        # The new user was not an admin, so they should not have the admin
        # interface link available
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_id('link-admin-index')

    @screenshots
    def _edit_account(self):
        edit_account_link = self.driver.find_element_by_id(
            'link-edit-account')
        edit_account_link.click()

        # The header says "Edit your account"
        h1s = self.driver.find_elements_by_tag_name('h1')[0]
        assert 'Edit your account' == h1s.text
        # There's no link back to the admin interface.
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_partial_link_text(
                'Back to admin interface')
        # There's no field to change your username.
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_css_selector('#username')
        # There's no checkbox to change the administrator status of your
        # account.
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_css_selector('#is-admin')
        # 2FA reset buttons at the bottom point to the user URLs for reset.
        totp_reset_button = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-totp')[0]
        assert ('/account/reset-2fa-totp' in
                totp_reset_button.get_attribute('action'))
        hotp_reset_button = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-hotp')[0]
        assert ('/account/reset-2fa-hotp' in
                hotp_reset_button.get_attribute('action'))

    @screenshots
    def _edit_user(self, username):
        # XXXX
        new_user_edit_links = filter(
            lambda el: el.get_attribute('data-username') == username,
            self.driver.find_elements_by_tag_name('a'))
        assert 1 == len(new_user_edit_links)
        new_user_edit_links[0].click()
        time.sleep(self.sleep_time)
        # The header says "Edit user "username"".
        h1s = self.driver.find_elements_by_tag_name('h1')[0]
        assert 'Edit user "{}"'.format(username) == h1s.text
        # There's a convenient link back to the admin interface.
        admin_interface_link = self.driver.find_element_by_partial_link_text(
            'Back to admin interface')
        assert re.search('/admin$', admin_interface_link.get_attribute('href'))
        # There's a field to change the user's username and it's already filled
        # out with the user's username.
        username_field = self.driver.find_element_by_css_selector('#username')
        assert username_field.get_attribute('placeholder') == username
        # There's a checkbox to change the administrator status of the user and
        # it's already checked appropriately to reflect the current status of
        # our user.
        username_field = self.driver.find_element_by_css_selector('#is-admin')
        assert (bool(username_field.get_attribute('checked')) ==
                False) # XXX
        # 2FA reset buttons at the bottom point to the admin URLs for
        # resettting 2FA and include the correct user id in the hidden uid.
        totp_reset_button = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-totp')[0]
        assert '/admin/reset-2fa-totp' in totp_reset_button.get_attribute(
            'action')
        totp_reset_uid = totp_reset_button.find_element_by_name('uid')
        #assert int(totp_reset_uid.get_attribute('value')) == 12 # XXXX
        assert totp_reset_uid.is_displayed() is False
        hotp_reset_button = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-hotp')[0]
        assert '/admin/reset-2fa-hotp' in hotp_reset_button.get_attribute(
            'action')

        hotp_reset_uid = hotp_reset_button.find_element_by_name('uid')
        #assert int(hotp_reset_uid.get_attribute('value')) == 12 # XXXX
        assert hotp_reset_uid.is_displayed() is False

    @screenshots
    def _admin_can_edit_new_user(self):
        # Log the new user out
        self._logout()

        time.sleep(self.sleep_time)
        self._login_user(self.admin, self.admin_pw, str(self.admin_user['totp'].now()))

        # Go to the admin interface
        admin_interface_link = self.driver.find_element_by_id(
            'link-admin-index')
        admin_interface_link.click()

        time.sleep(self.sleep_time)
        # Click the "edit user" link for the new user
        # self._edit_user(self.new_user['username'])
        new_user_edit_links = filter(
            lambda el: (el.get_attribute('data-username') ==
                        self.new_user['username']),
            self.driver.find_elements_by_tag_name('a'))
        assert len(new_user_edit_links) == 1
        new_user_edit_links[0].click()
        time.sleep(self.sleep_time)

        def can_edit_user():
            assert ('"{}"'.format(self.new_user['username']) in
                    self.driver.page_source)
        self.wait_for(can_edit_user)

        new_username = self.new_user['username'] + "2"

        username_field = self.driver.find_element_by_css_selector(
            'input[name="username"]')
        username_field.send_keys(new_username)
        update_user_btn = self.driver.find_element_by_css_selector(
            'button[type=submit]')
        update_user_btn.click()

        def can_edit_user2():
            assert ('"{}"'.format(new_username) in self.driver.page_source)
        self.wait_for(can_edit_user2)

        # Update self.new_user with the new username for the future tests
        self.new_user['username'] = new_username

        # Log the new user in with their new username
        self._logout()
        time.sleep(61)
        self._login_user(self.new_user['username'],
                         self.new_user['password'],
                         str(self.new_totp.now()))
        if not hasattr(self, 'accept_languages'):
            def found_sources():
                assert 'Sources' in self.driver.page_source
            self.wait_for(found_sources)

        # Log the admin user back in
        self._logout()
        time.sleep(61)
        self._login_user(self.admin, self.admin_pw, str(self.admin_user['totp'].now()))

        # Go to the admin interface
        admin_interface_link = self.driver.find_element_by_id(
            'link-admin-index')
        admin_interface_link.click()
        time.sleep(self.sleep_time)

        # Edit the new user's password
        self._edit_user(self.new_user['username'])
        new_password = self.driver.find_element_by_css_selector('#password') \
            .text.strip()
        self.new_user['password'] = new_password

        reset_pw_btn = self.driver.find_element_by_css_selector(
            '#reset-password')
        reset_pw_btn.click()
        time.sleep(self.sleep_time)

        def update_password_success():
            assert 'Password updated.' in self.driver.page_source

        # Wait until page refreshes to avoid causing a broken pipe error (#623)
        self.wait_for(update_password_success)

        # Log the new user in with their new password
        self._logout()
        self._login_user(self.new_user['username'],
                         self.new_user['password'],
                         str(self.new_totp.now()))
        self.wait_for(found_sources)

    @screenshots
    def _journalist_checks_messages(self):
        self.driver.get(self.journalist_location)

        # There should be 1 collection in the list of collections
        code_names = self.driver.find_elements_by_class_name('code-name')
        assert 0 != len(code_names), code_names
        assert 2 >= len(code_names), code_names

        if not hasattr(self, 'accept_languages'):
            # There should be a "1 unread" span in the sole collection entry
            unread_span = self.driver.find_element_by_css_selector(
                'span.unread')
            assert "1 unread" in unread_span.text

    @screenshots
    def _journalist_stars_and_unstars_single_message(self):
        # Message begins unstarred
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_id('starred-source-link-1')

        # Journalist stars the message
        self.driver.find_element_by_class_name('button-star').click()
        time.sleep(3)
        starred = self.driver.find_elements_by_id('starred-source-link-1')
        assert 1 == len(starred)

        # Journalist unstars the message
        self.driver.find_element_by_class_name('button-star').click()
        time.sleep(3)
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_id('starred-source-link-1')

    @screenshots
    def _journalist_selects_all_sources_then_selects_none(self):
        self.driver.find_element_by_id('select_all').click()
        checkboxes = self.driver.find_elements_by_id('checkbox')
        for checkbox in checkboxes:
            assert checkbox.is_selected()

        self.driver.find_element_by_id('select_none').click()
        checkboxes = self.driver.find_elements_by_id('checkbox')
        for checkbox in checkboxes:
            assert checkbox.is_selected() is False

    def _journalist_selects_the_first_source(self):
        self.driver.find_element_by_css_selector(
            '#un-starred-source-link-1').click()
        time.sleep(self.sleep_time)

    def _journalist_selects_documents_to_download(self):
        self.driver.find_element_by_id('select_all').click()

    @screenshots
    def _journalist_downloads_message(self):
        self._journalist_selects_the_first_source()

        submissions = self.driver.find_elements_by_css_selector(
            '#submissions a')
        assert 1 == len(submissions)

        file_url = submissions[0].get_attribute('href')

        # Downloading files with Selenium is tricky because it cannot automate
        # the browser's file download dialog. We can directly request the file
        # using urllib2, but we need to pass the cookies for the logged in user
        # for Flask to allow this.
        def cookie_string_from_selenium_cookies(cookies):
            cookie_strs = []
            for cookie in cookies:
                cookie_str = "=".join([cookie['name'], cookie['value']]) + ';'
                cookie_strs.append(cookie_str)
            return ' '.join(cookie_strs)

        raw_content = self.return_downloaded_content(file_url, cookie_string_from_selenium_cookies(
                self.driver.get_cookies()))

        decrypted_submission = self.gpg.decrypt(raw_content)
        submission = self._get_submission_content(file_url,
                                                  decrypted_submission)
        assert self.secret_message == submission

    def _journalist_composes_reply(self):
        reply_text = ('Thanks for the documents. Can you submit more '
                      'information about the main program?')
        self.wait_for(lambda: self.driver.find_element_by_id(
            'reply-text-field'
        ), timeout=60)
        self.driver.find_element_by_id('reply-text-field').send_keys(
            reply_text
        )

    def _journalist_sends_reply_to_source(self):
        #self._journalist_selects_the_first_source()  # XXXX
        self._journalist_composes_reply()
        self.driver.find_element_by_id('reply-button').click()
        time.sleep(self.sleep_time)

        if not hasattr(self, 'accept_languages'):
            assert ("Thanks. Your reply has been stored." in
                    self.driver.page_source)

    def _visit_edit_account(self):
        edit_account_link = self.driver.find_element_by_id(
            'link-edit-account')
        edit_account_link.click()

    def _visit_edit_secret(self, type):
        reset_form = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-' + type)[0]
        assert ('/account/reset-2fa-' + type in
                reset_form.get_attribute('action'))

        reset_button = self.driver.find_elements_by_css_selector(
            '#button-reset-two-factor-' + type)[0]
        reset_button.click()

    def _visit_edit_hotp_secret(self):
        self._visit_edit_secret('hotp')

    def _set_hotp_secret(self):
        hotp_secret_field = self.driver.find_elements_by_css_selector(
            'input[name="otp_secret"]')[0]
        hotp_secret_field.send_keys('123456')
        submit_button = self.driver.find_element_by_css_selector(
            'button[type=submit]')
        submit_button.click()

    def _visit_edit_totp_secret(self):
        self._visit_edit_secret('totp')

    def _admin_visits_add_user(self):
        add_user_btn = self.driver.find_element_by_css_selector(
            'button#add-user')
        add_user_btn.click()

    def _admin_visits_edit_user(self):
        new_user_edit_links = filter(
            lambda el: (el.get_attribute('data-username') ==
                        self.new_user['username']),
            self.driver.find_elements_by_tag_name('a'))
        assert len(new_user_edit_links) == 1
        new_user_edit_links[0].click()

        def can_edit_user():
            assert ('"{}"'.format(self.new_user['username']) in
                    self.driver.page_source)
        self.wait_for(can_edit_user)

    def _admin_visits_reset_2fa_hotp(self):
        hotp_reset_button = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-hotp')[0]
        assert ('/admin/reset-2fa-hotp' in
                hotp_reset_button.get_attribute('action'))
        hotp_reset_button.click()

    def _admin_visits_reset_2fa_totp(self):
        totp_reset_button = self.driver.find_elements_by_css_selector(
            '#reset-two-factor-totp')[0]
        assert ('/admin/reset-2fa-totp' in
                totp_reset_button.get_attribute('action'))
        totp_reset_button.click()

    def _admin_creates_a_user(self, hotp):
        add_user_btn = self.driver.find_element_by_css_selector(
            'button#add-user')
        add_user_btn.click()

        self.new_user = dict(
            username='dellsberg',
            password='pentagonpapers')

        self._add_user(self.new_user['username'],
                       is_admin=False,
                       hotp=hotp)

    def _journalist_delete_all(self):
        for checkbox in self.driver.find_elements_by_name(
                'doc_names_selected'):
            checkbox.click()
        self.driver.find_element_by_id('delete-selected').click()

    def _journalist_confirm_delete_all(self):
        self.wait_for(
            lambda: self.driver.find_element_by_id('confirm-delete'))
        confirm_btn = self.driver.find_element_by_id('confirm-delete')
        confirm_btn.click()


    def _journalist_continues_after_flagging(self):
        self.driver.find_element_by_id('continue-to-list').click()

    def _journalist_delete_none(self):
        self.driver.find_element_by_id('delete-selected').click()

    def _journalist_delete_all_javascript(self):
        self.driver.find_element_by_id('select_all').click()
        self.driver.find_element_by_id('delete-selected').click()
        self._alert_wait()

    def _journalist_delete_one(self):
        self.driver.find_elements_by_name('doc_names_selected')[0].click()
        self.driver.find_element_by_id('delete-selected').click()

    def _journalist_flags_source(self):
        self.driver.find_element_by_id('flag-button').click()

    def _journalist_visits_admin(self):
        self.driver.get(self.journalist_location + "/admin")

    def _journalist_fail_login(self):
        self.user, self.user_pw = db_helper.init_journalist()
        self._try_login_user(self.user.username, 'worse', 'mocked')

    def _journalist_fail_login_many(self):
        self.user, self.user_pw = "","" # XXXX
        for _ in range(5 + 1):
            self._try_login_user(self.user.username, 'worse', 'mocked')

    def _admin_enters_journalist_account_details_hotp(self, username,
                                                      hotp_secret):
        username_field = self.driver.find_element_by_css_selector(
            'input[name="username"]')
        username_field.send_keys(username)

        hotp_secret_field = self.driver.find_element_by_css_selector(
            'input[name="otp_secret"]')
        hotp_secret_field.send_keys(hotp_secret)

        hotp_checkbox = self.driver.find_element_by_css_selector(
            'input[name="is_hotp"]')
        hotp_checkbox.click()