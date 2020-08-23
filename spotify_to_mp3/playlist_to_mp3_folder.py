from __future__ import unicode_literals
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import logging
from pathlib import Path
import youtube_dl
import requests
import re
from requests_html import HTMLSession
import urllib.parse as parse
from html.parser import HTMLParser
import mutagen.id3 as id3
import mutagen
from PIL import Image

# import subprocess

logger = logging.getLogger('examples.add_tracks_to_playlist')
logging.basicConfig(level='DEBUG')
SPOTIFY_SCOPE = 'playlist-read-collaborative'
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
SPOTIPY_CLIENT_ID = 'd000a620575643119e08f77c2a256b3e'
SPOTIPY_CLIENT_SECRET = 'b4c9b338834a45908f2ca9f4119f1bff'
SPOTIPY_REDIRECT_URI = 'http://localhost:8888/callback/'
YOUTUBE_API_KEY = 'AIzaSyA4nZ_sRe1uvxt5l6kktsXm_yvRhaS31SM'
allowed_chars = re.compile(r"[a-zA-Z0-9_ $%@'()+=~!]")


def playlist_to_mp3_clt():
    client_creds = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
    try:
        sp = spotipy.Spotify(client_credentials_manager=client_creds,
                             auth_manager=SpotifyOAuth(scope=SPOTIFY_SCOPE,
                                                       client_id=SPOTIPY_CLIENT_ID,
                                                       client_secret=SPOTIPY_CLIENT_SECRET,
                                                       redirect_uri=SPOTIPY_REDIRECT_URI,
                                                       cache_path='./'))
    except:
        username = input('Please enter your Spotify Username: ')
        sp = spotipy.Spotify(client_credentials_manager=client_creds,
                             auth_manager=SpotifyOAuth(scope=SPOTIFY_SCOPE,
                                                       client_id=SPOTIPY_CLIENT_ID,
                                                       client_secret=SPOTIPY_CLIENT_SECRET,
                                                       redirect_uri=SPOTIPY_REDIRECT_URI,
                                                       username=username))

    playlists = sp.current_user_playlists()
    print('\nYour playlists:\n==============================')
    for i, item in enumerate(playlists['items']):
        print("%d %s" % (i, item['name']))

    playlist_i = input('\nEnter index (row number) of playlist you would like to convert to folder of MP3s: ')
    while not playlist_i.isdigit() or int(playlist_i) >= len(playlists['items']):
        playlist_i = input('Enter index (row number) of playlist you would like to convert to folder of MP3s: ')
    playlist_i = int(playlist_i)

    playlist = playlists['items'][playlist_i]
    playlist_name = playlist['name']
    print(f'\nSelected playlist: {playlist_name}')
    match = re.match(r'\W+', playlist_name, flags=re.ASCII)
    if match:
        playlist_name = input('This playlist would not be a valid folder name, '
                              'so please enter alternative name for playlist: ')
        match = re.match(r'\W+', playlist_name, flags=re.ASCII)
        while match:
            playlist_name = input('This playlist would not be a valid folder name, '
                                  'so please enter alternative name for playlist: ')
            match = re.match(r'\W+', playlist_name, flags=re.ASCII)

    try:
        folder_path = Path(input('\nEnter path to a parent folder for playlist: ')).resolve()
        folder_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        print(f'That path is not a valid path!')
        try_again = True
        while try_again:
            try:
                folder_path = Path(input('Please enter valid path to a parent folder for playlist: ')).resolve()
                folder_path.mkdir(parents=True, exist_ok=True)
                try_again = False
            except OSError:
                print(f'That path is not a valid path!')
    print(f'\nSelected parent folder: {folder_path}\n')

    playlist_obj = sp.playlist(playlist['id'])
    tracks_obj = playlist_obj['tracks']
    tracks = tracks_obj['items']

    while tracks_obj['next']:
        tracks_obj = sp.next(tracks_obj)
        tracks.extend(tracks_obj['items'])

    failed_downloads = []
    for track in tracks:
        track_name = track['track']['name']

        main_artist_name = track['track']['artists'][0]['name']
        album_name = track['track']['album']['name']
        artist_id = track['track']['artists'][0]['id']
        access_token = client_creds.get_access_token(as_dict=False)
        genres = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}',
                              headers={'Authorization': f'Bearer {access_token}'}).json()['genres']
        watch_urls = get_top_youtube_search_result_urls(f'{main_artist_name} {track_name} lyrics')

        failures = 0
        for url in watch_urls:
            try:
                download_song_from_youtube(track_name, main_artist_name, album_name, genres,
                                           playlist_name, url, folder_path)
                break
            except youtube_dl.utils.DownloadError:
                print(f'[ERROR youtube_dl] YouTube said: Unable to extract video data from link: {url}')
                failures += 1
        if failures == len(watch_urls):
            failed_downloads.append(f'{track_name} by {main_artist_name}')

        # failures = 0
        # for url in watch_urls:
        #     success = download_song_from_youtube(track_name, main_artist_name, album_name, genres,
        #                                          playlist_name, url, folder_path)
        #     if success:
        #         break
        #     else:
        #         failures += 1
        # if failures == len(watch_urls):
        #     failed_downloads.append(f'{track_name} by {main_artist_name}')

    if len(failed_downloads) > 0:
        print('The following songs failed to be downloaded:')
        for failure in failed_downloads:
            print(failure)


class MyLogger(object):
    def debug(self, msg):
        print(f'[DEBUG] {msg}')

    def warning(self, msg):
        print(f'[WARNING] {msg}')

    def error(self, msg):
        print(f'[ERROR] {msg}')


def my_hook(d):
    if d['status'] == 'finished':
        print('Done downloading, now converting ...')


def replace_bad_chars(string, good_chars):
    char_list = []
    for c in string:
        if not re.match(good_chars, c):
            char_list.append('-')
        else:
            char_list.append(c)
    return ''.join(char_list)


def download_song_from_youtube(track_name, artist_name, album_name, genres, playlist_name, watch_url,
                               destination_folder):
    track_name = track_name.replace(':', '-')

    file_name = replace_bad_chars(f'{track_name} - {artist_name}', allowed_chars)
    mp3_path = f'{destination_folder}/{playlist_name}/{file_name}.mp3'
    if Path(mp3_path).is_file():
        print(f'{mp3_path} already exists, skipping download from youtube')
        return

    ydl_opts = {
        'outtmpl': f'{destination_folder}/{playlist_name}/{file_name}.%(ext)s',
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192'}],
        'writethumbnail': True,
        'logger': MyLogger(),
        'progress_hooks': [my_hook]
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([watch_url])

    mp3_path_no_ext = f'{destination_folder}/{playlist_name}/{file_name}'
    cover_art_path = None
    if Path(f'{mp3_path_no_ext}.jpg').is_file():
        cover_art_path = f'{mp3_path_no_ext}.jpg'
    elif Path(f'{mp3_path_no_ext}.jpeg').is_file():
        cover_art_path = f'{mp3_path_no_ext}.jpeg'
    elif Path(f'{mp3_path_no_ext}.webp').is_file():
        cover_art_path = f'{mp3_path_no_ext}.webp'
    elif Path(f'{mp3_path_no_ext}.png').is_file():
        cover_art_path = f'{mp3_path_no_ext}.png'

    add_id3_data_to_mp3(mp3_path, track_name, artist_name, album_name, genres, cover_art_path)

    # success = True
    # try:
    #     subprocess.run(['youtube-dl',
    #                     '--extract-audio',
    #                     '--format', 'bestaudio/best',
    #                     '--output', f'{destination_folder}/{playlist_name}/{track_name} - {artist_name}.mp3',
    #                     '--audio-format', 'mp3'
    #                     '--audio-quality', '192',
    #                     '--add-metadata',
    #                     watch_url],
    #                    capture_output=True, check=True)
    # except subprocess.CalledProcessError as error:
    #     print('[ERROR] youtube-dl failed due to following error:')
    #     print(str(error.stderr, encoding='utf-8'))
    #     print('Exit code of youtube-dl command:', error.returncode)
    #     success = False

    # return success


def add_id3_data_to_mp3(mp3_path, track_name, artist_name, album_name, genres, cover_art_path=None,
                        remove_cover_art=True):
    mp3_path = Path(mp3_path).resolve()
    cover_art_path = Path(cover_art_path).resolve()

    try:
        mp3_meta = id3.ID3(mp3_path)
    except mutagen.id3.ID3NoHeaderError:
        mp3_meta = mutagen.File(mp3_path, easy=True)
        mp3_meta.add_tags()
        mp3_meta.save()
        mp3_meta = id3.ID3(mp3_path)

    # track
    mp3_meta.add(id3.TIT2(text=track_name, encoding=3))
    mp3_meta.add(id3.TSOT(text=track_name, encoding=3))

    # artist
    mp3_meta.add(id3.TOPE(text=artist_name, encoding=3))
    mp3_meta.add(id3.TPE1(text=artist_name, encoding=3))
    mp3_meta.add(id3.TSO2(text=artist_name, encoding=3))

    # album
    mp3_meta.add(id3.TALB(text=album_name, encoding=3))
    mp3_meta.add(id3.TOAL(text=album_name, encoding=3))
    mp3_meta.add(id3.TSOA(text=album_name, encoding=3))

    # genre
    if len(genres) > 0:
        mp3_meta.add(id3.TCON(text=genres[0], encoding=3))

    # comment
    mp3_meta.add(id3.COMM(text='finessed', desc=u'finessed', encoding=3, lang='ENG'))

    # cover art
    if cover_art_path:
        ext = Path(cover_art_path).suffix[1:]
        just_name = Path(cover_art_path).stem
        parent_dir = Path(cover_art_path).parent

        if ext == 'jpg' or ext == 'jpeg' or ext == 'webp' or ext == 'png':
            if ext == 'jpg' or ext == 'jpeg' or ext == 'webp':
                with Image.open(cover_art_path).convert("RGB") as cover_art:
                    cover_art.save(f"{parent_dir / just_name}.png", "png")
                    og_cover_art = str(cover_art_path)
                    cover_art_path = f"{parent_dir / just_name}.png"

            with open(cover_art_path, 'rb') as cover_art:
                mp3_meta.add(id3.APIC(encoding=3,
                                      mime=f'image/png',
                                      type=3,
                                      desc='youtube thumbnail',
                                      data=cover_art.read()))

            if remove_cover_art:
                Path(cover_art_path).unlink()
                Path(og_cover_art).unlink()

    mp3_meta.save()


class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.videoIds = None

    # def handle_starttag(self, tag, attrs):
    #     print("Encountered a start tag:", tag)
    #
    # def handle_endtag(self, tag):
    #     print("Encountered an end tag :", tag)

    def handle_data(self, data):
        if 'window["ytInitialData"]' in data:
            cleaner_data = data.strip().split('\n')[0]
            videoIds = {}
            matches_iter = re.finditer(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', cleaner_data)
            index = 0
            for match in matches_iter:
                just_id = match.group(1)
                if just_id not in videoIds:
                    videoIds[index] = just_id
                    index += 1

            self.videoIds = videoIds


def get_top_youtube_search_result_urls(query_string='', max_results=6, max_retries=6):
    url_encoded_query = parse.quote(query_string)

    session = HTMLSession()
    parser = MyHTMLParser()

    try_again = True
    while max_retries > 0 and try_again:
        try:
            resp = session.get(f'https://www.youtube.com/results?search_query={url_encoded_query}')
            parser.feed(resp.text)

            try_again = False
        except (OSError):
            print(f'[ERROR] Failed to search on Youtube for "{query_string}" and retrieve video ids, retrying...')
            max_retries -= 1

    if try_again:
        print(f'[ERROR] Failed to search on Youtube for "{query_string}" and retrieve video ids, giving up')
        return

    videoIds = parser.videoIds

    # regular python dicts after 3.7 support insertion ordering but this is just to make sure older python versions work
    urls = [f"https://www.youtube.com/watch?v={videoIds[i]}" for i in range(max_results)]

    return urls


# def get_top_youtube_search_result_urls_old_and_lame(query_string='', max_results=6, max_retrys=6):
#     resp_json = requests.get('https://www.googleapis.com/youtube/v3/search',
#                              params={'part': 'snippet',
#                                      'maxResults': str(max_results),
#                                      'q': query_string,
#                                      'key': YOUTUBE_API_KEY},
#                              headers={'Accept': 'application/json'}).json()
#
#     if 'items' not in resp_json:
#         while max_retrys > 0 and 'items' not in resp_json:
#             resp_json = requests.get('https://www.googleapis.com/youtube/v3/search',
#                                      params={'part': 'snippet',
#                                              'maxResults': str(max_results),
#                                              'q': query_string,
#                                              'key': YOUTUBE_API_KEY},
#                                      headers={'Accept': 'application/json'}).json()
#             max_retrys -= 1
#
#     if 'items' not in resp_json:
#         print(f'Unable to search for "{query_string}" on youtube')
#         return []
#
#     search_results = resp_json['items']
#     urls = []
#     for result in search_results:
#         if 'videoId' in result['id']:
#             urls.append(f"https://www.youtube.com/watch?v={(result['id']['videoId'])}")
#     return urls


if __name__ == '__main__':
    playlist_to_mp3_clt()
