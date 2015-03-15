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
from retrying import retry
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

@retry(stop_max_attempt_number=10, wait_fixed=500)
def remove_db(db_file):
    os.remove(db_file)


class ClientTest(TestCase):
    def setUp(self):
        if os.path.isfile(db_file):
            remove_db(db_file)
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