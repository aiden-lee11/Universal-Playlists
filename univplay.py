from flask import Flask, request, url_for, session, redirect, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask_session import Session
import uuid, json, uuid, os, time, requests
from functions import *
from applepymusic import AppleMusicClient

app = Flask(__name__)
app.secret_key = os.urandom(64)
TOKEN_INFO = "token_info"
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
description = 'Created By Universal Playlists'

caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)
    
def session_cache_path():
    return caches_folder + session.get('uuid')

@app.before_request
def setup_session():
    if not session.get('uuid'):
        session['uuid'] = str(uuid.uuid4())
    if session.get('apple_signed') != True:
        session['apple_signed'] = False
                     

@app.route('/')
def index():

    auth_manager = create_spotify_oauth()

    if request.args.get("code"):
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')

    if not auth_manager.get_cached_token():
        auth_url = auth_manager.get_authorize_url()
        return render_template('spotify_sign_in.html', auth_url = auth_url)
    
    if session.get('apple_signed') == False:
        return render_template('apple_sign_in.html')
    
    return redirect('display_playlist')
    
@app.route('/apple_sign_in/', methods=['POST'])
def handle_user_token():
    try:
        data = request.json
        session['apple_user_token'] = data.get('userToken')
        return redirect(url_for('display_playlist'))
    except Exception as e:
        return str(e), 500
    
@app.route('/display_playlist')
def display_playlist():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    sp = spotipy.Spotify(auth_manager=auth_manager)
    apple_client = AppleMusicClient(team_id= 'TEAM_ID', 
                                    key_id='KEY_ID', 
                                    private_key='PRIVATE_KEY', 
                                    access_token=session['apple_user_token'],
                                    timeout=120)
    total_spotify_playlists = sp.user_playlists(sp.me()['id'])['items']
    spotify_playlist_names_ids = []
    for item in total_spotify_playlists: 
        if item['owner']['id'] == sp.me()['id']:
            spotify_playlist_names_ids.append((item['name'], item['id']))
            
    apple_playlists = apple_client.user_playlists(limit=50)['data']
    apple_playlist_names_ids =[]
    for item in apple_playlists:
        if item['attributes']['canEdit'] and item['attributes']['isPublic']:
            apple_playlist_names_ids.append((item['attributes']['name'], item['attributes']['playParams']['globalId'], item['id']))
    return render_template('playlist.html', spotify_playlists=spotify_playlist_names_ids, apple_music_playlists=apple_playlist_names_ids) 
    
@app.route('/display_tracks', methods = ['GET'])
def display_tracks():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    sp = spotipy.Spotify(auth_manager=auth_manager)
    spotify_playlist_name_id = clean(request.args.get('spotify_playlist')) # set this to be the spotify playlist
    apple_music_playlist_name_globalId_id =  clean(request.args.get('apple_music_playlist')) # set this to be the apple playlist
    playlist_action = request.args.get('playlist_action')
    songs_in_spotify_playlist = get_track_details(spotify_playlist_name_id[1], returner='name',session_cache_path=session_cache_path)
    apple_url = f'https://music.apple.com/us/playlist/{apple_music_playlist_name_globalId_id[2]}/{apple_music_playlist_name_globalId_id[1]}'
    songs_in_apple_music_playlist = get_songs_from_apple_playlist(playlist_url=apple_url, returner='songs')
    return render_template('songs.html', 
                           songs_spotify_playlist = songs_in_spotify_playlist,
                           songs_apple_music_playlist = songs_in_apple_music_playlist,
                           spotify_playlist_name_id = spotify_playlist_name_id,
                           apple_music_playlist_name_globalId_id = apple_music_playlist_name_globalId_id,
                           spotify_user_id = sp.me()['id'],
                           playlist_action = playlist_action
                           ) 

@app.route('/spotify_write_new_playlist', methods=['POST']) # Working as of 8/13/23
def spotify_write_new_playlist():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    sp = spotipy.Spotify(auth_manager=auth_manager)
    playlist_name = request.form.get('playlist_name')
    spotify_user_id = request.form.get('spotify_user_id')
    spotify_playlist_name_id = clean(request.form.get('spotify_playlist_name_id'))
    apple_music_playlist_name_globalId_id = clean(request.form.get('apple_music_playlist_name_globalId_id'))
    apple_url = f'https://music.apple.com/us/playlist/{apple_music_playlist_name_globalId_id[2]}/{apple_music_playlist_name_globalId_id[1]}'
    try:
        spotify_playlist_track_uris = (get_track_details(playlist_id=spotify_playlist_name_id[1], returner='uri', session_cache_path=session_cache_path))
        apple_music_playlist_track_uris = (apple_songs_to_spotify_uris(playlist_url=apple_url, token=auth_manager.get_access_token()['access_token']))
        track_uris = list(set(spotify_playlist_track_uris + apple_music_playlist_track_uris))
    except Exception as e:
        return str(e)
    sp.user_playlist_create(user=spotify_user_id, name= playlist_name, description=description)
    for item in sp.user_playlists(spotify_user_id)['items']:
        if item['owner']['id'] == spotify_user_id and item['description'] == description and item['name'] == playlist_name:
            playlist_id = item['id']
    spotify_add_songs(playlist_id=playlist_id, track_uris=track_uris, session_cache_path=session_cache_path)
    return render_template('sign_out.html', playlist_name = playlist_name)

@app.route('/apple_write_new_playlist', methods=['POST']) # Working as of 8/13/23
def apple_write_new_playlist():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    token = session['apple_user_token']
    apple_client = AppleMusicClient(team_id= 'TEAM_ID', 
                                    key_id='KEY_ID', 
                                    private_key='PRIVATE_KEY', 
                                    access_token=session['apple_user_token'],
                                    timeout=120)
    playlist_name = request.form.get('playlist_name')
    spotify_playlist_name_id = clean(request.form.get('spotify_playlist_name_id'))
    apple_music_playlist_name_globalId_id = clean(request.form.get('apple_music_playlist_name_globalId_id'))
    apple_url = f'https://music.apple.com/us/playlist/{apple_music_playlist_name_globalId_id[2]}/{apple_music_playlist_name_globalId_id[1]}'
    spotify_playlist_track_isrcs_album_name = (get_track_details(playlist_id=spotify_playlist_name_id[1], returner='isrc_album_name', session_cache_path=session_cache_path))
    try:
        apple_music_playlist_track_isrc = get_track_details_from_uris(track_uris=apple_songs_to_spotify_uris(playlist_url=apple_url, token=auth_manager.get_access_token()['access_token']), returner='isrc',
                                                                session_cache_path=session_cache_path,)
    except Exception as e:
        print('inside this block')
        return str(e)
    info_to_add = difference_with_tuples(apple_music_playlist_track_isrc, spotify_playlist_track_isrcs_album_name) # Holds isrcs in spot 1 of tuple and album names in spot 2
    ids = list(set(get_apple_id_from_isrc(isrcs = [i[0] for i in info_to_add], album_names=[i[1] for i in info_to_add], token=token) + clean_ids(get_songs_from_apple_playlist(playlist_url=apple_url, returner='id'))))
    apple_client.user_playlist_create(name=playlist_name, description=description)
    time.sleep(7.5)
    apple_playlists = apple_client.user_playlists(limit=50)['data']
    for item in apple_playlists:    
        try:
            if item['attributes']['name'] == playlist_name and item['attributes']['description']['standard'] == description:
                new_playlist_id = item['id']
                break
        except:
            pass
    apple_client.user_playlist_add_tracks(id=new_playlist_id, track_ids=ids)
    return render_template('sign_out.html', playlist_name = playlist_name)

@app.route('/spotify_write_existing_playlist', methods=['POST']) # Working as of 8/13/23
def spotify_write_existing_playlist():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    spotify_playlist_name_id = clean(request.form.get('spotify_playlist_name_id'))
    apple_music_playlist_name_globalId_id = clean(request.form.get('apple_music_playlist_name_globalId_id'))
    apple_url = f'https://music.apple.com/us/playlist/{apple_music_playlist_name_globalId_id[2]}/{apple_music_playlist_name_globalId_id[1]}'
    try:
        spotify_playlist_track_uris = (get_track_details(playlist_id=spotify_playlist_name_id[1], returner='uri', session_cache_path=session_cache_path))
        apple_music_playlist_track_uris = (apple_songs_to_spotify_uris(playlist_url=apple_url, token=auth_manager.get_access_token()['access_token']))
        tracks_to_add = difference(apple_music_playlist_track_uris, spotify_playlist_track_uris)
        spotify_add_songs(playlist_id=spotify_playlist_name_id[1],track_uris=tracks_to_add, session_cache_path=session_cache_path)
    except Exception as e:
        return str(e)

    return render_template('sign_out.html', playlist_name = spotify_playlist_name_id[0])

@app.route('/apple_write_existing_playlist', methods=['POST']) # Working as of 8/13/23
def apple_write_existing_playlist():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    apple_token=session['apple_user_token']
    spotify_token = auth_manager.get_access_token()['access_token']
    spotify_playlist_name_id = clean(request.form.get('spotify_playlist_name_id'))
    apple_music_playlist_name_globalId_id = clean(request.form.get('apple_music_playlist_name_globalId_id'))
    apple_url = f'https://music.apple.com/us/playlist/{apple_music_playlist_name_globalId_id[2]}/{apple_music_playlist_name_globalId_id[1]}'
    try:
        apple_client = AppleMusicClient(team_id= 'TEAM_ID', 
                                    key_id='KEY_ID', 
                                    private_key='PRIVATE_KEY', 
                                    access_token=session['apple_user_token'],
                                    timeout=120)
        spotify_uris = get_track_details(playlist_id=spotify_playlist_name_id[1], returner='uri', session_cache_path=session_cache_path)
        apple_uris = apple_songs_to_spotify_uris(playlist_url=apple_url, token=spotify_token)
        add_to_apple = uri_to_appleID(track_uris=difference(spotify_uris, apple_uris),apple_token=apple_token, session_cache_path=session_cache_path)
        apple_client.user_playlist_add_tracks(id=apple_music_playlist_name_globalId_id[2], track_ids=add_to_apple)
    except Exception as e:
        return str(e)
    return render_template('sign_out.html', playlist_name = apple_music_playlist_name_globalId_id[0])

@app.route('/add_to_both', methods= ['POST']) # Working as of 8/13/23
def add_to_both():
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_path=session_cache_path())
    if not auth_manager.get_cached_token():
        return redirect('/')
    apple_token=session['apple_user_token']
    spotify_token = auth_manager.get_access_token()['access_token']
    apple_client = AppleMusicClient(team_id= 'TEAM_ID', 
                                    key_id='KEY_ID', 
                                    private_key='PRIVATE_KEY', 
                                    access_token=session['apple_user_token'],
                                    timeout=120)
    spotify_playlist_name_id = clean(request.form.get('spotify_playlist_name_id'))
    apple_music_playlist_name_globalId_id = clean(request.form.get('apple_music_playlist_name_globalId_id'))
    apple_url = f'https://music.apple.com/us/playlist/{apple_music_playlist_name_globalId_id[2]}/{apple_music_playlist_name_globalId_id[1]}'
    spotify_uris = get_track_details(playlist_id=spotify_playlist_name_id[1], returner='uri', session_cache_path=session_cache_path)
    apple_uris = apple_songs_to_spotify_uris(playlist_url=apple_url, token=spotify_token)
    add_to_spotify = difference(apple_uris, spotify_uris)
    add_to_apple = uri_to_appleID(track_uris=difference(spotify_uris, apple_uris),apple_token=apple_token, session_cache_path=session_cache_path)
    apple_client.user_playlist_add_tracks(id=apple_music_playlist_name_globalId_id[2], track_ids=add_to_apple)
    spotify_add_songs(playlist_id=spotify_playlist_name_id[1],track_uris=add_to_spotify, session_cache_path=session_cache_path)
    return render_template('sign_out.html', playlist_name = f"{spotify_playlist_name_id[0]} and {apple_music_playlist_name_globalId_id[0]}")
        
@app.route('/sign_out')
def sign_out():
    try:
        os.remove(session_cache_path())
        session.clear()
    except OSError as e:
        print ("Error: %s - %s." % (e.filename, e.strerror))
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
    