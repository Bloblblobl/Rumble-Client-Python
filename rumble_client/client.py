from datetime import datetime
import json
import requests
import requests.exceptions

class Client(object):
    def __init__(self, base_url):
        self.user_auth = None
        self.base_url = base_url

    def register(self, username, password, handle):
        """
        :return:
        """
        params = dict(username=username, password=password, handle=handle)
        url = self.base_url + '/user'
        r = requests.post(url=url, params=params)
        r.raise_for_status()
        return r.json()

    def login(self, username, password):
        """
        :return:
        """
        params = dict(username=username, password=password)
        url = self.base_url + '/active_user'
        r = requests.post(url=url, params=params)
        r.raise_for_status()
        self.user_auth = r.json()['user_auth']
        
    def logout(self):
        """
        :return:
        """
        url = self.base_url + '/active_user'
        headers = dict(Authorization=self.user_auth)
        r = requests.delete(url=url, headers=headers)
        r.raise_for_status()
        
    def send_message(self, name, message):
        """
        :return:
        """
        params = dict(message=message)
        url = self.base_url + '/message/' + name
        headers = dict(Authorization=self.user_auth)
        r = requests.post(url=url, params=params, headers=headers)
        r.raise_for_status()
        
    def get_messages(self, name, start, end):
        for ts in (start, end):
            assert isinstance(ts, datetime)
        url = self.base_url + '/messages/{}/{}/{}'.format(name, start.isoformat(), end.isoformat())
        headers = dict(Authorization=self.user_auth)
        r = requests.get(url=url, headers=headers)
        r.raise_for_status()
        return r.json()
    
    def create_room(self, name):
        url = self.base_url + '/room/' + name
        headers = dict(Authorization=self.user_auth)
        r = requests.post(url=url, headers=headers)
        r.raise_for_status()
    
    def destroy_room(self, name):
        url = self.base_url + '/room/' + name
        headers = dict(Authorization=self.user_auth)
        r = requests.delete(url=url, headers=headers)
        r.raise_for_status()

    def join_room(self, name):
        params = dict(name=name)
        url = self.base_url + '/room_member'
        headers = dict(Authorization=self.user_auth)
        r = requests.post(url=url, headers=headers, params=params)
        r.raise_for_status()

    def leave_room(self, name):
        params = dict(name=name)
        url = self.base_url + '/room_member'
        headers = dict(Authorization=self.user_auth)
        r = requests.delete(url=url, headers=headers, params=params)
        r.raise_for_status()
    
    def get_rooms(self):
        url = self.base_url + '/rooms'
        headers = dict(Authorization=self.user_auth)
        r = requests.get(url=url, headers=headers)
        r.raise_for_status()
    
    def get_room_members(self, name):
        url = self.base_url + '/room_members/' + name
        headers = dict(Authorization=self.user_auth)
        r = requests.get(url=url, headers=headers)
        r.raise_for_status()
