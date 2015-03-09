from datetime import datetime, timedelta
import os
import threading
import time
import json
from unittest import TestCase
import uuid

from flask import app
from mock import Mock
import sys
import sqlite3
from werkzeug.datastructures import Headers
from rumble_client.client import Client


script_dir = os.path.dirname(__file__)
server_dir = os.path.join(script_dir, '../../Rumble-Server/rumble_server')

sys.path.insert(0, server_dir)

import api
import server
from multiprocessing import Process


port = 8888
db_file = os.path.join(os.environ['TEMP'], 'rumble.db')

def start_server():
    server.db_file = db_file
    # Reset singleton every time
    server.get_instance()

    host = 'localhost'
    api.the_app.run(host=host, port=port)

class ClientTest(TestCase):
    def setUp(self):
        if os.path.isfile(db_file):
            os.remove(db_file)
        cmd = 'sqlite3 {} < {}/rumble_schema.sql'.format(db_file, server_dir)
        os.system(cmd)

        self.p = Process(target=start_server)
        self.p.start()
        self.client = Client('http://localhost:{}'.format(port))
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()

    def tearDown(self):
        if self.client.user_auth != None:
            self.client.logout()
            self.client.user_auth = None
        self.p.terminate()
        self.conn.close()

    def _register_test_user(self, username='saar', password='passwurd', handle='Saar'):
        try:
            self.client.register(username, password, handle)
        except Exception as e:
            raise

    def _login_test_user(self, username='saar', password='passwurd', handle='Saar'):
        self._register_test_user(username, password, handle)
        try:
            self.client.login(username, password)
        except Exception as e:
            raise

    def test_create_room_success(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)

    def test_create_room_unauthorize_user(self):
        response = self.client.create_room('room0')
        self.assertEqual(401, response.status_code)

    def test_create_room_already_exists(self):
        self._login_test_user()
        self.client.create_room('room0')
        response = self.client.create_room('room0')
        self.assertEqual(400, response.status_code)

    def test_destroy_room_success(self):
        self._login_test_user()
        self.client.create_room('room0')
        response = self.client.destroy_room('room0')
        self.assertEqual(200, response.status_code)

    def test_destroy_room_unauthorize_user(self):
        self.client.create_room('room0')
        response = self.client.destroy_room('room0')
        self.assertEqual(401, response.status_code)

    def test_destroy_room_does_not_exist(self):
        self._login_test_user()
        response = self.client.destroy_room('room0')
        self.assertEqual(404, response.status_code)

    def test_join_room_success(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)

    def test_join_room_does_not_exist(self):
        self._login_test_user()
        response = self.client.join_room('room0')
        self.assertEqual(404, response.status_code)

    def test_leave_room_success(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.leave_room('room0')
        self.assertEqual(200, response.status_code)

    def test_leave_room_not_joined(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.leave_room('room0')
        self.assertEqual(404, response.status_code)

    def test_send_message_success(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)
        message = 'test'
        response = self.client.send_message('room0', message)
        self.assertEqual(200, response.status_code)

        self.cur.execute("SELECT * FROM message WHERE room_id = (SELECT id FROM room WHERE name = 'room0')")
        room_messages = self.cur.fetchall()
        self.assertItemsEqual(message, room_messages[0][4])

    def test_send_message_wrong_room(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        message = 'test'
        response = self.client.send_message('room0', message)
        self.assertEqual(401, response.status_code)

    def test_send_message_no_such_room(self):
        self._login_test_user()
        message = 'test'
        response = self.client.send_message('room0', message)
        self.assertEqual(404, response.status_code)

    def test_get_messages_no_message(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)

        start = datetime.now().replace(microsecond=0)
        end = start + timedelta(days=1)

        response = self.client.get_messages('room0', start, end)
        final = response['result']
        self.assertItemsEqual([], final)

    def test_get_messages_one_message(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)
        message = 'test'
        response = self.client.send_message('room0', message)
        self.assertEqual(200, response.status_code)

        start = datetime.now().replace(microsecond=0)
        end = start + timedelta(days=1)

        response = self.client.get_messages('room0', start, end)
        final = response['result'][0][2]
        self.assertItemsEqual(message, final)

    def test_get_messages_multiple_messages(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)
        message = 'test'

        start = datetime.utcnow().replace(microsecond=0)
        end = start + timedelta(seconds=4)
        for x in xrange(3):
            response = self.client.send_message('room0', message)
            self.assertEqual(200, response.status_code)
            time.sleep(1)

        response = self.client.get_messages('room0', start, end)
        final = len(response['result'])
        self.assertEqual(2, final)

        start = datetime.utcnow().replace(microsecond=0)
        end = start + timedelta(seconds=10)
        for x in xrange(3):
            response = self.client.send_message('room0', message + str(x))
            self.assertEqual(200, response.status_code)
            time.sleep(1)

        response = self.client.get_messages('room0', start, end)
        expected = [['Saar', 'test0'],
                    ['Saar', 'test1'],
                    ['Saar', 'test2']]
        actual = response['result']
        final = [x[1:] for x in actual]
        self.assertItemsEqual(expected, final)

    def test_get_rooms_no_rooms(self):
        self._login_test_user()
        response = self.client.get_rooms()
        self.assertEqual([], response['result'])

    def test_get_rooms_one_room(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.get_rooms()
        self.assertEqual(['room0'], response['result'])

    def test_get_rooms_multiple_rooms(self):
        self._login_test_user()
        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.create_room('room1')
        self.assertEqual(200, response.status_code)
        response = self.client.create_room('room2')
        self.assertEqual(200, response.status_code)
        response = self.client.get_rooms()
        self.assertItemsEqual(['room0', 'room1', 'room2'], response['result'])

    def test_get_room_members_one_member(self):
        self._login_test_user()

        response = self.client.create_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.join_room('room0')
        self.assertEqual(200, response.status_code)
        response = self.client.get_room_members('room0')
        self.assertEqual(['Saar'], response['result'])

    # def test_register_success(self):
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM user")
    #         users = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, users)
    #
    #     response = self._register_test_user()
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual('OK', result)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM user")
    #         users = cur.fetchall()
    #         expected = [(1, 'Saar_Sayfan', 'passwurd', 'Saar')]
    #         self.assertEqual(expected, users)
    #
    # def test_register_username_exists(self):
    #     # Register once
    #     self._register_test_user()
    #
    #     # try to register again with the same user name
    #     response = self._register_test_user()
    #     self.assertEqual(400, response.status_code)
    #     message = json.loads(response.data)['message']
    #     self.assertEqual('Username Saar_Sayfan is already taken', message)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM user")
    #         users = cur.fetchall()
    #         expected = [(1, 'Saar_Sayfan', 'passwurd', 'Saar')]
    #         self.assertEqual(expected, users)
    #
    # def test_register_handle_exists(self):
    #     # Register once
    #     self._register_test_user()
    #
    #     # try to register again with the another user name, but same handle
    #     response = self._register_test_user(username='Gigi')
    #     self.assertEqual(400, response.status_code)
    #     message = json.loads(response.data)['message']
    #     self.assertEqual('Handle Saar is already taken', message)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM user")
    #         users = cur.fetchall()
    #         expected = [(1, 'Saar_Sayfan', 'passwurd', 'Saar')]
    #         self.assertEqual(expected, users)
    #
    # def test_user_login_success(self):
    #     self._register_test_user()
    #
    #     post_data = dict(username='Saar_Sayfan',
    #                      password='passwurd', )
    #
    #     # Mock uuid
    #     uuid4_orig = uuid.uuid4
    #     try:
    #         m = Mock()
    #         m.hex = '12345'
    #         uuid.uuid4 = lambda: m
    #         response = self.test_app.post('/active_user', data=post_data)
    #         self.assertEqual(200, response.status_code)
    #         user_auth = json.loads(response.data)['user_auth']
    #         self.assertTrue('12345', user_auth)
    #     finally:
    #         uuid.uuid4 = uuid4_orig
    #
    # def test_user_login_wrong_password(self):
    #     self._register_test_user()
    #
    #     post_data = dict(username='Saar_Sayfan',
    #                      password='passwird', )
    #     response = self.test_app.post('/active_user', data=post_data)
    #     self.assertEqual(401, response.status_code)
    #
    # def test_user_login_unregistered(self):
    #     post_data = dict(username='Saar_Sayfan',
    #                      password='passwurd', )
    #
    #     response = self.test_app.post('/active_user', data=post_data)
    #     self.assertEqual(401, response.status_code)
    #     message = json.loads(response.data)['message']
    #     self.assertEqual('Invalid username or password', message)
    #
    # def test_user_login_already_logged_in(self):
    #     self._register_test_user()
    #
    #     post_data = dict(username='Saar_Sayfan',
    #                      password='passwurd', )
    #
    #     response = self.test_app.post('/active_user', data=post_data)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/active_user', data=post_data)
    #     self.assertEqual(400, response.status_code)
    #
    # def test_create_room_success(self):
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, rooms)
    #
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = [(1, 'room0')]
    #         self.assertEqual(expected, rooms)
    #
    # def test_create_room_already_exists(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = [(1, 'room0')]
    #         self.assertEqual(expected, rooms)
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(400, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = [(1, 'room0')]
    #         self.assertEqual(expected, rooms)
    #
    # def test_create_room_unauthorized_user(self):
    #     response = self.test_app.post('/room/room0', headers=self.bad_auth)
    #     self.assertEqual(401, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, rooms)
    #
    # def test_join_room_success(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    # def test_join_room_already_joined(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0')
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(400, response.status_code)
    #
    # def test_join_room_no_such_room(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0')
    #
    #     response = self.test_app.post('/room_member', data=post_data, headers=auth)
    #     self.assertEqual(404, response.status_code)
    #
    # def test_join_room_unauthorized_user(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0')
    #
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=self.bad_auth)
    #     self.assertEqual(401, response.status_code)
    #
    # def test_get_rooms_no_rooms(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.get('/rooms', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual([], result)
    #
    # def test_get_rooms_one_room(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/rooms', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual(['room0'], result)
    #
    # def test_get_rooms_multiple_rooms(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/room/room1', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/rooms', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual(['room0', 'room1'], result)
    #
    # def test_get_room_members_no_member(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/room_members/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     result = json.loads(response.data)['result']
    #     self.assertEqual([], result)
    #
    # def test_get_room_members_one_member(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/room_members/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     result = json.loads(response.data)['result']
    #     self.assertEqual(['Saar'], result)
    #
    # def test_get_room_members_multiple_members(self):
    #     auth = self._login_test_user()
    #     auth2 = self._login_test_user('Guy_Sayfan', 'passwird', 'Guy')
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth2)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/room_members/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     result = set(json.loads(response.data)['result'])
    #     expected = {'Saar', 'Guy'}
    #     self.assertEqual(expected, result)
    #
    # def test_destroy_room_success(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.delete('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, rooms)
    #
    # def test_destroy_room_with_messages_success(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0', message='message')
    #
    #     response = self.test_app.post('/message/room0',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = [(1, 1, 'message')]
    #         self.assertEqual(expected, messages)
    #
    #     response = self.test_app.delete('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, rooms)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, messages)
    #
    # def test_destroy_room_does_not_exist(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.delete('/room/room0', headers=auth)
    #     self.assertEqual(404, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT * FROM room")
    #         rooms = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, rooms)
    #
    # def test_destroy_room_unauthorized_user(self):
    #     auth = self._login_test_user()
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.delete('/room/room0', headers=self.bad_auth)
    #     self.assertEqual(401, response.status_code)
    #
    # def test_handle_message_success(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0')
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0', message='message')
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, messages)
    #
    #     response = self.test_app.post('/message/room0',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = [(1, 1, 'message')]
    #         self.assertEqual(expected, messages)
    #
    # def test_handle_message_unauthorized_user(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0', message='message')
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/message/room0',
    #                                   data=post_data,
    #                                   headers=self.bad_auth)
    #     self.assertEqual(401, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, messages)
    #
    # def test_handle_message_room_does_not_exist(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0', message='message')
    #
    #     response = self.test_app.post('/message/room0',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(404, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, messages)
    #
    # def test_handle_message_not_member(self):
    #     auth = self._login_test_user()
    #     post_data = dict(name='room0', message='message')
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.post('/message/room0',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(401, response.status_code)
    #
    #     with self.conn:
    #         cur = self.conn.cursor()
    #         cur.execute("SELECT room_id, user_id, message FROM message")
    #         messages = cur.fetchall()
    #         expected = []
    #         self.assertEqual(expected, messages)
    #
    # def test_get_messages_unauthorized_user(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/messages/room0/start/end', headers=self.bad_auth)
    #     self.assertEqual(401, response.status_code)
    #
    #
    # def test_get_messages_room_does_not_exist(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.get('/messages/room0/start/end', headers=auth)
    #     self.assertEqual(404, response.status_code)
    #
    # def test_get_messages_not_member(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/messages/room0/start/end', headers=auth)
    #     self.assertEqual(401, response.status_code)
    #
    # def test_get_messages_no_messages(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     start = '2014-12-24T00:00:00'
    #     end = '2014-12-25T00:00:00'
    #
    #     response = self.test_app.get('/messages/room0/{}/{}'.format(start, end), headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual({}, result)
    #
    # def test_get_messages_one_message(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     start = datetime.now().replace(microsecond=0)
    #     end = start + timedelta(days=1)
    #
    #     start = start.isoformat()
    #     end = end.isoformat()
    #
    #     post_data = dict(message='TEST MESSAGE')
    #     response = self.test_app.post('/message/room0',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     response = self.test_app.get('/messages/room0/{}/{}'.format(start, end), headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual('TEST MESSAGE', result.values()[0][1])
    #
    # def test_get_room_members_multiple_messages(self):
    #     auth = self._login_test_user()
    #
    #     response = self.test_app.post('/room/room0', headers=auth)
    #     self.assertEqual(200, response.status_code)
    #
    #     post_data = dict(name='room0')
    #     response = self.test_app.post('/room_member',
    #                                   data=post_data,
    #                                   headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     start = datetime.utcnow().replace(microsecond=0)
    #
    #     # send 3 messages 1 second apart
    #     for i in range(3):
    #         post_data = dict(message='TEST MESSAGE {}'.format(i))
    #         response = self.test_app.post('/message/room0',
    #                                       data=post_data,
    #                                       headers=auth)
    #         self.assertEqual(200, response.status_code)
    #         time.sleep(1)
    #
    #     # no messages in range
    #     end = start
    #     response = self.test_app.get('/messages/room0/{}/{}'.format(start.isoformat(), end.isoformat()), headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual({}, result)
    #
    #     # 1 message in range
    #     end = start + timedelta(seconds=1)
    #     response = self.test_app.get('/messages/room0/{}/{}'.format(start.isoformat(), end.isoformat()), headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     self.assertEqual('TEST MESSAGE 0', result.values()[0][1])
    #
    #     # all messages in range
    #     end = start + timedelta(seconds=4)
    #     response = self.test_app.get('/messages/room0/{}/{}'.format(start.isoformat(), end.isoformat()), headers=auth)
    #     self.assertEqual(200, response.status_code)
    #     result = json.loads(response.data)['result']
    #     values = sorted(result.values())
    #     self.assertEqual('TEST MESSAGE 0', values[0][1])
    #     self.assertEqual('TEST MESSAGE 1', values[1][1])
    #     self.assertEqual('TEST MESSAGE 2', values[2][1])