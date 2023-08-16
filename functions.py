from flask import Flask, request, url_for, session, redirect, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time 
import os
from flask_session import Session
import uuid, json, re
from typing import Iterable, Any, Tuple
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import requests, re, json
import webbrowser
from applepymusic import AppleMusicClient



caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)


def get_track_details(playlist_id, returner, session_cache_path):
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    sp = spotipy.Spotify(auth_manager=auth_manager)
    track_details = []
    iter = 0
    while True:
        offset = iter * 50 
        iter += 1
        current = sp.playlist_tracks(playlist_id, limit = 50, offset = offset)['items']
        for item in current:
            if returner == 'isrc':
                track_detail = item['track']['external_ids'][returner]
            elif returner =='name' or returner == 'uri':
                track_detail = item['track'][returner]
            elif returner == 'isrc_album_name':
                track_detail = (item['track']['external_ids']['isrc'], item['track']['album']['name'])
            elif returner == 'isrc_uri':
                track_detail = item['track']['external_ids']['isrc'], item['track']['uri']
            elif returner == 'album_name':
                track_detail = item['track']['album']['name']
                
            track_details.append(track_detail)
        if(len(current) < 50):
            break
    return track_details


def spotify_add_songs(playlist_id, track_uris,session_cache_path):
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    sp = spotipy.Spotify(auth_manager=auth_manager)
    iter = 0 
    end = False
    while True:
        pos = iter * 100
        offset = (iter + 1) * 100
        iter += 1
        if offset > len(track_uris):
            offset = len(track_uris)
            end = True
        tracks = track_uris[pos:offset] 
        sp.playlist_add_items(playlist_id=playlist_id, items=tracks)
        if end:
            break
    
def create_spotify_oauth():
    redirect_uri = url_for('index', _external=True, _scheme=request.scheme)
    return SpotifyOAuth(
        client_id="CLIENT_ID",
        client_secret="CLIENT_SECRET",
        redirect_uri=redirect_uri,
        scope="playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public",  
        cache_path=session_cache_path(),
        show_dialog=True,   
    )

def session_cache_path():
    return caches_folder + session.get('uuid')

def clean(dirty):
    return dirty[2:-2].replace("', '", ",").translate({ord(i): None for i in "[]"}).split(',') # gets rid of the junk surrounding the id and the name to make it easier to display

def difference(list1, list2):
    s = set(list2)
    return [x for x in list1 if x not in s]

def difference_with_tuples(norm_list, tuple_list):
    diff = []
    for i in range(len(tuple_list)):
        if tuple_list[i][0] not in norm_list:
            diff.append(tuple_list[i])
    return diff
            
class AppleSong:
    def __init__(self, title: str, artists: list, length: str):
        self.title = title.strip()
        self.artists = artists
        self.length = length.strip()
        
    def length_in_ms(self) -> int:
        string = self.length
        return int(string.split(':')[0]) * 60 * 1000 + int(string.split(':')[1]) * 1000
    
    def search_str(self) -> str:
        artists = "".join(self.artists).strip()
        title = self.title.strip()
                
        return f'{title} {artists}'

def get_songs_from_apple_playlist(playlist_url, returner):
    try:
        r =  requests.get(playlist_url, stream=True)
        
        soup = BeautifulSoup(r.content, 'html.parser')
        divs = soup.find_all('meta', {'property': 'music:song'})
        songs = []
    except Exception:
        print('here')
    for div in divs:
        try:
            url = re.search(r'https://[^"]+', str(div)).group()
            url_req = requests.get(str(url), stream=True)
            song_soup = BeautifulSoup(url_req.content, 'html.parser')
            song_info = str(song_soup.find('meta', {'name': 'apple:description'}))
            song_id = str(song_soup.find('meta', {'name': 'apple:content_id'}))
            if returner == 'class':
                songs.append(split_info(song_info=song_info, returner = 'class'))
            elif returner == 'songs':
                songs.append(split_info(song_info=song_info, returner = 'songs'))
            else: #returner == id
                songs.append(song_id)
        except Exception:
            print('no here')
        else: 
            pass
            
    return songs 

def get_spotify_uris(songs, token):
    list = []
    
    for song in songs:
        # Make search request to Spotify
        try:
            r = requests.get(f'https://api.spotify.com/v1/search?q={song.search_str()}&type=track', 
                            headers={'Authorization': f'Bearer {token}'}, stream=True) 
        except:
            print(f'\033[31m Internal error while searching for song: {song.search_str()}')

        data = r.json()
        
        if(r.status_code != 200 and r.status_code != 201 and r.status_code != 404):
            print(f'\033[31m Spotify API Error while searching for song: {song.search_str()}. ({r.status_code} {r.json()["error"]["message"]})')
            continue

        if len(data['tracks']['items']) == 0:
            print(f'\033[33m No results for spotify search:  {song.search_str()}')
            continue
        
        # Loop through the results and get the uri of the first match
        for is_last, item in signal_last(r.json()['tracks']['items']):
 
            spotify_name = normalize_string(item['name'])
            apple_name = normalize_string(song.title)
            len_diff = song.length_in_ms() - item['duration_ms']
            title_diff = SequenceMatcher(None, spotify_name, apple_name).ratio() # difference in title
            same_title = apple_name in spotify_name or spotify_name in apple_name
            if -2000 < len_diff < 2000 and (same_title or title_diff > 0.8):
                list.append(item['uri'])
                break
            
        time.sleep(1.5)
    return list

def apple_songs_to_spotify_uris(playlist_url, token):
    songs = get_songs_from_apple_playlist(playlist_url=playlist_url, returner='class')
    return get_spotify_uris(songs=songs, token=token)
            
def split_info(song_info, returner):
    song_artist_pattern = r'Listen to (.+?) by (.+?) on Apple Music'
    song_artist_match = re.search(song_artist_pattern, song_info)

    if song_artist_match:
        song_name = song_artist_match.group(1)
        artist = song_artist_match.group(2)

    # Extracting the duration
    duration_pattern = r'Duration: (\d+:\d+)'
    duration_match = re.search(duration_pattern, song_info)

    if duration_match:
        duration = duration_match.group(1)
    # return (song_name, artist, duration)
    return AppleSong(title=song_name, artists=artist, length=duration) if returner.lower() == 'class' else (song_name)
    
def normalize_string(string):
    string = string.lower()
    string = re.sub('[^a-z0-9 ]', '', string)
    string = re.sub("[\(\[].*?[\)\]]", "", string)

    return string

def signal_last(it:Iterable[Any]) -> Iterable[Tuple[bool, Any]]:
    iterable = iter(it)
    ret_var = next(iterable)
    for val in iterable:
        yield False, ret_var
        ret_var = val
    yield True, ret_var

def get_apple_id_from_isrc(isrcs, album_names, token):
    apple_client = AppleMusicClient(team_id= 'TEAM_ID', 
                                    key_id='KEY_ID', 
                                    private_key='PRIVATE_KEY', 
                                    access_token=session['apple_user_token'],
                                    timeout=120)
    ids = []
    print(len(isrcs))
    for i in range(len(isrcs)):
        song_details = apple_client.get_songs_by_isrc(isrc=isrcs[i])['data']
        if len(song_details) == 1:
            ids.append(song_details['id'])
        else:
            for song in song_details:
                if song['attributes']['albumName'] == album_names[i]:
                    ids.append(song['id'])
    return ids

def get_track_details_from_uris(track_uris, returner, session_cache_path):
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    sp = spotipy.Spotify(auth_manager=auth_manager)
    track_details = []
    if returner == 'isrc':
        for track_uri in track_uris:
                track_details.append(sp.track(track_uri)['external_ids']['isrc'])
    elif returner == 'album_name':
        for track_uri in track_uris:
                track_details.append(sp.track(track_uri)['album']['name'])
        
    return track_details

def clean_ids(ids):
    stripped_ids =[]
    
    for id in ids:
        pattern = r'<meta content="(\d+)" name="apple:content_id"/>'

        match = re.search(pattern, id)
        if match:
            stripped_ids.append(match.group(1))
            
    return stripped_ids

def uri_to_appleID(track_uris, apple_token, session_cache_path):
    isrcs = get_track_details_from_uris(track_uris=track_uris, returner='isrc', session_cache_path=session_cache_path)
    album_names = get_track_details_from_uris(track_uris=track_uris, returner='album_name', session_cache_path=session_cache_path)
    return get_apple_id_from_isrc(isrcs=isrcs,album_names=album_names, token=apple_token)
    