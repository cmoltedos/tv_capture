import os
import requests, pickle
import datetime
import re
import time
import ujson
from Crypto.Cipher import AES
from optparse import OptionParser
from pdb import set_trace

USER_AGENT = 'Mozilla/5.0'

def input_args():
    parser = OptionParser()
    parser.add_option("-c", "--channel",
                      dest="channel", default='tvn',
                      help="Channel id [default: tvn].\n"
                           "Options: tvn, mega")
    (options, args) = parser.parse_args()
    return options


def canal_13_token_decrypt(token_encripted):
    letters_1 = list(token_encripted)
    letters_2 = list(token_encripted)
    letters_amount = len(letters_1)
    factor_1 = int(int(time.time() * 1000) / 3600000)
    factor_2 = int(int(time.time() * 1000) / 3600000) - 1
    for i in range(letters_amount, 0, -1):
        pos = i - 1
        var_1 = pos * factor_1 % letters_amount
        var_2 = pos * factor_2 % letters_amount
        letters_1[pos], letters_1[var_1] = letters_1[var_1], letters_1[pos]
        letters_2[pos], letters_2[var_2] = letters_2[var_2], letters_2[pos]
    string2 = ''.join(letters_1)
    sub_string = string2[letters_amount - 2:letters_amount]
    if sub_string == 'OK':
        return string2[:-2]
    string2 = ''.join(letters_2)
    return string2[:-2]


def decrypt_ts_files(content, key_uri):
    key = requests.get(url=key_uri)
    key_content = key.content
    decipher = AES.new(key_content, AES.MODE_CBC, b'0'*16)
    content_decipher = decipher.decrypt(content)
    return content_decipher


class Stream(object):

    def __init__(self, channel=None, link=None, account_data=None):
        assert channel is not None or link is not None
        self.channel = channel if channel is not None else self.get_link_channel(link)
        self.is_live = True
        self.login_required = False
        self.rsession = self.create_request_session()
        self.token_function, live_link, login_function = self.channel_config()
        self.link = link if link else live_link
        try:
            self.token = self.token_function()
            if account_data and self.channel in account_data:
                login_function(*account_data[self.channel])
            if self.channel == '13':
                self.links_by_resolution = self.get_13_init_urls_stream()
            else:
                self.config_data = self.get_stream_config_data()
                self.links_by_resolution = self.get_init_urls_stream()
        except AttributeError:
            self.links_by_resolution = {}

    def get_link_channel(self, link):
        if 'www.13.cl' in link:
            return '13'
        if 'www.tvn.cl' in link:
            return 'tvn'
        if 'www.mega.cl' in link:
            return 'mega'
        if 'www.chilevision.cl' in link:
            return 'chv'
        return None

    def channel_config(self):
        channel_config = {
            'tvn': (self.get_token_tvn,
                    '57a498c4d7b86d600e5461cb',
                    lambda x, y: None),
            'mega': (self.get_token_mega,
                     'https://www.mega.cl/senal-en-vivo/',
                     self.login_mega),
            '13': (self.get_token_13,
                   'https://www.13.cl/en-vivo',
                   self.login_13),
            'chv': (self.get_token_chv,
                    'https://www.chilevision.cl/senal-online',
                    lambda x, y: None)
        }
        if self.channel not in channel_config:
            raise IOError('Channel not supported')
        return channel_config[self.channel]

    def get_token_chv(self, ommit_cache=False):
        html = self.rsession.get(url=self.link).text
        if 'online' in self.link:
            player_js_url = re.search("id=\"mdstrm-player\".*?src='(.*?)'", html, re.DOTALL).group(1)
            player_js = self.rsession.get(url=player_js_url).text
            token = re.search("token = '(.*?)';", player_js, re.DOTALL).group(1)
            self.channel_id = re.search("id = '(.*?)';", player_js, re.DOTALL).group(1)
            self.is_live = True
        else:
            self.channel_id = re.search("data-id=\"(.*?)\"", html, re.DOTALL).group(1)
            self.is_live = False
            return None

        token_cache_filename = f'token_cache_{self.channel}_{self.channel_id}.txt'
        if not ommit_cache and os.path.exists(token_cache_filename):
            with open(token_cache_filename) as token_file:
                token = token_file.read()
                print(f"CACHE HIT: CHV token ({token})")
                return token
        with open(token_cache_filename, 'w') as token_file:
            token_file.write(token)
        print(f"CACHE MISS: New CHV token ({token})")
        return token

    def get_token_13(self, ommit_cache=False):
        if 'en-vivo' in self.link:
            self.is_live = True
        else:
            self.is_live = False
            return None
        html = self.rsession.get(url=self.link).text
        encripted_token = re.search("function playerLive.*?"
                                    "'([a-zA-Z0-9]*)'\) \|\| ", html,
                                    re.DOTALL).group(1)
        self.channel_id = canal_13_token_decrypt(encripted_token)

        token_cache_filename = f'token_cache_{self.channel}_{self.channel_id}.txt'
        if not ommit_cache and os.path.exists(token_cache_filename):
            with open(token_cache_filename) as token_file:
                token = token_file.read()
                print(f"CACHE HIT: 13 token ({token})")
                return token
        token_url = 'https://past-server.nedp.io/token/cl-canal13-canal13'
        params = {'rsk': self.channel_id}
        result = self.rsession.get(url=token_url, params=params)
        token = result.json()['token']
        with open(token_cache_filename, 'w') as token_file:
            token_file.write(token)
        print(f"CACHE MISS: New 13 token ({token})")
        return token

    def get_token_mega(self, ommit_cache=False):
        html = self.rsession.get(url=self.link).text
        self.channel_id, server_key = re.search("video = {id: '(.*?)'.*?"
                                                "serverKey : '(.*?)'", html,
                                                re.DOTALL).groups()
        if 'en-vivo' in self.link:
            self.is_live = True
        else:
            self.is_live = False
        token_cache_filename = f'token_cache_{self.channel}_{self.channel_id}.txt'

        if not ommit_cache and os.path.exists(token_cache_filename):
            with open(token_cache_filename) as token_file:
                token = token_file.read()
                print(f"CACHE HIT: Mega token ({token})")
                return token
        params = {
            'id': self.channel_id, 'type': 'live' if self.is_live else 'media',
            'process': 'access_token', 'key': server_key, 'ua': USER_AGENT
        }

        headers = {'Origin': 'https://www.mega.cl', 'User-Agent': USER_AGENT}
        url = 'https://api.mega.cl/api/v1/mdstrm'
        result = self.rsession.get(url=url, params=params, headers=headers)
        token = result.json()['access_token']
        with open(token_cache_filename, 'w') as token_file:
            token_file.write(token)
        print(f"CACHE MISS: New Mega token ({token})")
        return token

    def get_token_tvn(self, ommit_cache=False):
        if self.link.startswith('http'):
            result = self.rsession.get(url=self.link).text
            self.link = re.search("url: '(.*?)'", result).group(1)
            self.channel_id = self.link.split('/')[-1][:-5] # remove .m3u8
            self.is_live = False
            return None
        else:
            self.is_live = True

        self.channel_id = self.link
        token_cache_filename = f'token_cache_{self.channel}_{self.channel_id}.txt'
        if not ommit_cache and os.path.exists(token_cache_filename):
            with open(token_cache_filename) as token_file:
                token = token_file.read()
                print(f"CACHE HIT: TVN token ({token})")
                return token
        token_url = 'https://token.tvn.cl/'
        params = {'url': self.link}
        result = self.rsession.get(url=token_url, params=params).text
        var = re.search('.*MediastreamPlayer\d?\(DivId, (.*?)\);',
                        result).group(1)
        token = re.search(f"^.*?{var} = .*?access_token: '(.*?)',", result,
                          re.DOTALL).group(1)

        with open(token_cache_filename, 'w') as token_file:
            token_file.write(token)
        print(f"CACHE MISS: New TVN token ({token})")
        return token

    def get_stream_config_data(self):
        config_data = dict()
        params = {
            'jsapi': "true", 'autoplay': "true",
            'access_token': self.token, 'mse': "true"
        }
        if self.is_live:
            url = f'https://mdstrm.com/live-stream/{self.channel_id}'
        else:
            url = f'https://mdstrm.com/embed/{self.channel_id}'
            params = {}
        retries = 3
        while retries:
            result = self.rsession.get(url=url, params=params)
            result_html = result.text
            try:
                config_data['account_id'] = re.search(
                    ".*\"accountID\":\"([A-Za-z0-9]*)\"", result_html, re.DOTALL
                ).group(1)
                break
            except:
                print("[WARNING] Actual token didn't work, getting new one.")
                self.token = self.token_function(ommit_cache=True)
                params['access_token'] = self.token
                retries -= 1
                if retries == 0:
                    set_trace()
                    raise ConnectionError("Token fail to get data")

        config_data['playback_id'] = re.search(".*MDSTRMPID = '([A-Za-z0-9]*)'", result_html, re.DOTALL).group(1)
        config_data['session_id'] = re.search(".*MDSTRMSID = '([A-Za-z0-9]*)'", result_html, re.DOTALL).group(1)
        config_data['unique_id'] = re.search(".*MDSTRMUID = '([A-Za-z0-9]*)'", result_html, re.DOTALL).group(1)
        config_data['version'] = re.search(".*VERSION = '(.*?)'", result_html, re.DOTALL).group(1)
        return config_data

    def get_init_urls_stream(self):
        params = {
            'uid': self.config_data['unique_id'],
            'sid': self.config_data['session_id'],
            'pid': self.config_data['playback_id'],
            'av': self.config_data['version'],
            'access_token': self.token,
            'an': 'screen', 'at': 'web-app', 'ref': '',
            'res': '1280x720', 'dnt': 'true'
        }
        if self.is_live:
            url = f'https://mdstrm.com/live-stream-playlist/{self.channel_id}.m3u8'
            response = self.rsession.get(url=url, params=params)
            result = response.text
        else:
            url = f'https://mdstrm.com/video/{self.channel_id}.m3u8'
            response = self.rsession.get(url=url)
            if response.status_code == 401:
                print("[INFO] Login required")
                self.login_required = True
                headers = {'User-Agent': USER_AGENT}
                response = self.rsession.get(url=url, params=params,
                                             headers=headers)
            result = response.text
        links_by_resolution = dict(re.findall("RESOLUTION=[0-9]{3,4}x([0-9]{3,4}).*?\n([a-zA-Z0-9:/\-\.&?=_%]+)", result, re.DOTALL))

        for resolution, link in links_by_resolution.items():
            if link.startswith('http'):
                break
            link_server = re.search("&es=(.*?)&", link, re.DOTALL).group(1)
            links_by_resolution[resolution] = f'https://{link_server}{link}'

        resolutions = sorted(links_by_resolution.keys(), key=lambda x: int(x))
        print(f"[INFO] Available resolutions: {resolutions}")
        return links_by_resolution

    def get_available_resolution(self):
        return sorted(self.links_by_resolution.keys(),
                      key=lambda x: int(x), reverse=True)

    def get_13_init_urls_stream(self):
        if self.is_live:
            base_url = 'https://cl-canal13-canal13-live.ned.media'
            url = f'{base_url}/live.m3u8'
            params = {'iut': self.token}
            result = self.rsession.post(url=url, params=params)
            manifest_url = result.json()['manifestUrl']
            url2 = f'{base_url}{manifest_url}'
            url3 = f'{base_url}/v1/'
        else:
            result = self.rsession.get(url=self.link).text
            find_video = re.search("articuloVideo = \"(.*?)\"", result, re.DOTALL)
            if not find_video:
                return {}
            url2 = find_video.group(1)
            url3 = url2.replace('main.m3u8', '')
            self.channel_id = url3.split('/')[-2]

        result = self.rsession.get(url=url2).text
        links_by_resolution = dict(re.findall("RESOLUTION=[0-9]{3,4}x([0-9]{3,4}).*?\n(.*?)\n", result, re.DOTALL))

        for resolution in links_by_resolution:
            links_by_resolution[resolution] = url3 + links_by_resolution[resolution].lstrip('./')
        print(f"[INFO] Available resolutions: {links_by_resolution.keys()}")
        return links_by_resolution

    def get_streaming_file_list(self, resolution):
        link_by_resolution = self.links_by_resolution[resolution]
        if self.channel == 'mega' and self.is_live:
            origin = 'https://www.mega.cl'
            headers = {'Origin': origin, 'User-Agent': USER_AGENT}
        elif self.login_required:
            headers = {'User-Agent': USER_AGENT}
        else:
            headers = {}
        result = self.rsession.get(url=link_by_resolution, headers=headers)
        if result.status_code != 200:
            raise ConnectionError(f"Error retrieving ({result.status_code}) data for {link_by_resolution}")
        result_content = result.text
        duration_sec = int(re.search("^.*?TARGETDURATION:(\d*)", result_content, re.DOTALL).group(1))
        encrypt_data = re.search("^.*?EXT-X-KEY:(.*?)\n", result_content, re.DOTALL)
        if encrypt_data:
            key_uri = re.search(".*?URI=\"(.*?)\"", encrypt_data.group(1)).group(1)
        else:
            key_uri = None
        links = re.findall("\n(.*?\.ts.*?)\n", result_content)
        if not links[0].startswith('http'):
            prev_code = '/'.join(link_by_resolution.split('/')[:-1])
            links = [f'{prev_code}/{link}' for link in links]
            key_uri = f'{prev_code}/{key_uri}'
        return links, duration_sec, key_uri

    def store_n_seconds(self, seconds=10, resolution='720', folder = ''):
        total_time = batch_time = 0
        prev_advance_time_percentage = prev_advance_ts_percentaje = 0
        result_filename = f'result_{self.channel}_{self.channel_id}.ts'
        result_route = os.path.join(folder, result_filename)
        consume_ts_urls = set()
        with open(result_route, 'wb') as _:
            pass
        yield 0
        while total_time < seconds:
            time.sleep(int(batch_time * 0.8))
            ts_urls, sec_each, key_uri = self.get_streaming_file_list(resolution)
            total_ts = len(set(ts_urls) - consume_ts_urls)
            if batch_time == 0:
                batch_time = total_ts * sec_each
            print(f"[INFO] Downloading {total_ts} video sections")
            for i, ts_url in enumerate(ts_urls):
                if ts_url in consume_ts_urls:
                    continue
                consume_ts_urls.add(ts_url)
                total_time += sec_each
                if self.login_required:
                    headers = {'User-Agent': USER_AGENT}
                else:
                    headers = {}
                content = self.rsession.get(url=ts_url, headers=headers).content
                if key_uri:
                    content = decrypt_ts_files(content, key_uri)
                with open(result_route, 'ab') as result_file:
                    result_file.write(content)

                advance_time_percentage = int(total_time / seconds *100)
                advance_ts_percentaje = int((i+1) / total_ts * 100)
                if self.is_live and seconds == float('inf'):
                    yield total_time
                elif self.is_live and advance_time_percentage > prev_advance_time_percentage:
                    prev_advance_time_percentage = advance_time_percentage
                    print(f'[INFO] {round(total_time/60, 2)} minutes recorded')
                    yield advance_time_percentage
                elif not self.is_live and advance_ts_percentaje > prev_advance_ts_percentaje:
                    prev_advance_ts_percentaje = advance_ts_percentaje
                    print(f'[INFO] {i+1} sections downloaded')
                    yield advance_ts_percentaje
            if not self.is_live:
                break

        yield 100

    def login_13(self, username, password):
        login_url = 'https://login.13.cl/user/login'
        params = {
            "name": username, "pass": password, "form_id": "user_login"
        }
        response = self.rsession.post(url=login_url, data=params)
        check_elements = re.search("postMessage\(\'(.*?)\'", response.text, re.DOTALL)
        check_code = check_elements.group(1).split('|')[-2]
        check_url = f'https://www.13.cl/login13/check/{check_code}'
        response2 = self.rsession.post(url=check_url)
        return None

    def login_mega(self, username, password):
        params = {
            'client_id': 'mga-web', 'response_type': 'code', 'scope': 'openid',
            'redirect_uri': self.link
        }
        login_form_url = 'https://sso.mega.cl/auth/realms/megamedia/protocol/openid-connect/auth'
        response = self.rsession.get(url=login_form_url, params=params)

        login_url = re.search("form id=\"kc-form-login\".*?action=\"(.*?)\"", response.text, re.DOTALL).group(1)
        login_url = login_url.replace('&amp;', '&')
        data_form = {
            "username": username, "password": password
        }
        response2 = self.rsession.post(url=login_url, data=data_form)
        sso_token_url = 'https://sso.mega.cl/auth/realms/megamedia/protocol/openid-connect/token'
        data_form2 = {
            'code': response2.url.split('code=')[-1],
            'grant_type': 'authorization_code',
            'client_id': params['client_id'],
            'redirect_uri': params['redirect_uri']
        }
        response3 = self.rsession.post(url=sso_token_url, data=data_form2)
        return None

    def create_request_session(self):
        rsession = requests.session()
        cookies_filename = f'cookies_{self.channel}'
        if os.path.exists(cookies_filename):
            with open(cookies_filename, 'rb') as f:
                rsession.cookies.update(pickle.load(f))
        return rsession

    def __exit__(self, exc_type, exc_val, exc_tb):
        cookies_filename = f'cookies_{self.channel}'
        with open(cookies_filename, 'wb') as f:
            pickle.dump(self.rsession.cookies, f)
        return None


class MegaPrograms(object):

    def __init__(self):
        self.link = 'https://www.mega.cl/programas/'
        self.cache_filename = 'mega_programs_cache.json'

    def get_cache(self):
        if not os.path.exists(self.cache_filename):
            print('[Warning] No cache file')
            return dict()
        with open(self.cache_filename) as cache_file:
            return ujson.loads(cache_file.read())

    def set_cache(self, programs):
        with open(self.cache_filename, 'w') as cache_file:
            cache_file.write(ujson.dumps(programs))
        return None

    def get_programs(self):
        result = requests.get(url=self.link).text
        programs = re.findall("<li class=\"col-item\">.*?href=\"([a-z0-9:/\-\.]+)\" target=\"_self\">",
                              result, re.DOTALL)
        programs_dict = self.get_cache()
        for program_url in programs:
            program_url2 = re.search("(https://[a-z0-9\-\.]+?/[a-z0-9\-]+?/"
                                    "[a-z0-9\-]+).*", program_url)
            if program_url2:
                program_url = program_url2.group(1)
            else:
                continue
            program_chapters_url = program_url + '/capitulos/'
            result2 = requests.get(url=program_chapters_url)
            if result2.status_code != 200:
                continue
            program_html = result2.text
            title = re.search("<h1 class=\"title\">(.*?)</h1>", program_html,
                              re.DOTALL).group(1)
            print(f"[INFO] Getting chapters for {title}")
            if title not in programs_dict:
                programs_dict[title] = list()
                cache_chapters = set()
            else:
                cache_chapters = set(programs_dict[title])
            new_chapters = list()
            params = {'page': 0, 'isAjax': True}
            while True:
                result3 = requests.get(url=program_chapters_url, params=params)
                chapters_per_page = re.findall(
                    "<li class=\"col-item\">.*?href=\"([a-z0-9:/\-\.]+?)\""
                    ".*?<p>(.*?)</p>.*?<h3>(.*?)</h3>",
                    result3.text, re.DOTALL)
                if len(chapters_per_page) == 0:
                    break
                if len(set(chapters_per_page) - cache_chapters) == 0:
                    break
                for chapter in chapters_per_page:
                    if chapter in cache_chapters:
                        break
                    new_chapters.append(chapter)
                params['page'] += 1
            if new_chapters:
                programs_dict[title] = new_chapters + programs_dict[title]
                self.filter_out_not_available_chapters(programs_dict[title])
        self.set_cache(programs_dict)
        return programs_dict

    def filter_out_not_available_chapters(self, chapters):
        print(f"[INFO] Filtering unavailable chapters ({len(chapters)})")
        left_i = 0
        right_i = step_i = len(chapters)-1
        get_section_type = lambda c: re.search("\"articleSection\": "
                                               "\"([a-zA-Z]*)\"",
                                               requests.get(url=c[0]).text,
                                               re.DOTALL).group(1)
        # binary search for the first not video
        while True:
            section_type = get_section_type(chapters[left_i])
            if left_i == 0 and section_type != 'Videos':
                print('[INFO] All chapters are unavailable')
                del chapters[:]
                break
            next_section_type = get_section_type(chapters[right_i])
            if left_i == 0 and next_section_type == 'Videos':
                print('[INFO] All chapters are available')
                break
            step_i = int(step_i / 2) if step_i > 1 else step_i
            if left_i == right_i - 1 and section_type != next_section_type:
                print(f'[INFO] {len(chapters[right_i:])} chapters are unavailable')
                del chapters[right_i:]
                break
            elif section_type != 'Videos':
                right_i = left_i
                left_i -= step_i
            else:
                left_i += step_i
        return None


def do_work(opt):
    # stream = MegaPrograms()
    # programs = stream.get_programs()
    link = 'https://www.13.cl/programas/masterchef-celebrity/capitulos/masterchef-celebrity-chile-capitulo-16-dulce-reto'
    stream = Stream(link=link)
    # stream = Stream(channel=opt.channel.lower())
    resolution = str(input(f'Insert a resolution: '))
    [i for i in stream.store_n_seconds(resolution=resolution)]


if __name__ == '__main__':
    init = datetime.datetime.now()
    opt = input_args()
    do_work(opt)
    print(f"[INFO] Process finish in in {datetime.datetime.now() - init}")