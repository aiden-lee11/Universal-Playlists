# -*- coding: utf-8 -*-

"""
Apple Music Python Client

Unofficial python wrapper for Apple Music API, not endorsed by Apple in any way

Subject to (frequent!) Apple Music API/documentation changes

https://developer.apple.com/documentation/applemusicapi

Apple Music API Objects:
https://developer.apple.com/documentation/applemusicapi/apple_music_api_objects

HTTP Status Codes:
https://developer.apple.com/documentation/applemusicapi/http_status_codes
"""

import datetime
import jwt
import json
import requests


BASE_URL = 'https://api.music.apple.com'

API_VERSION = 'v1'

TIMEOUT_SECONDS = 30


# Track types
# The possible values are songs, music-videos, library-songs, or library-music-videos.
# https://developer.apple.com/documentation/applemusicapi/libraryplaylistrequesttrack
TRACK_TYPE_SONGS = 'songs'
TRACK_TYPE_MUSIC_VIDEOS = 'music-videos'
TRACK_TYPE_LIBRARY_SONGS = 'library-songs'
TRACK_TYPE_LIBRARY_MUSIC_VIDEOS = 'library-music-videos'


class AppleMusicClient(object):

    # Client-specific JSON Web Token
    # https://pyjwt.readthedocs.io/en/latest/
    # <str>
    developer_token = None

    def __init__(self, team_id, key_id, private_key, access_token=None,
                 base_url=BASE_URL, api_version=API_VERSION,
                 timeout=TIMEOUT_SECONDS):
        """
        Params:
            `team_id` <str>
            `key_id` <str>
            `private_key` <str> something like:
                "-----BEGIN PRIVATE KEY-----\nYOUR KEY DATA HERE\n-----END PRIVATE KEY-----"
            `access_token` <str>
            `base_url` <str>
            `api_version` <str>
            `timeout` <int>
        """
        self.team_id = team_id
        self.key_id = key_id
        self.private_key = private_key
        self.user_access_token = access_token
        self.base_url = base_url
        self.api_version = api_version
        self.timeout = timeout
        self.developer_token = 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjgyNEE3QUIyQVQifQ.eyJpYXQiOjE2OTE2Mjc0OTgsImV4cCI6MTcwNzE3OTQ5OCwiaXNzIjoiSlRWWEEzN1RLMiJ9.W0ofUb-wPxjvQqbqXxCQ-HHRqsrnGiacrtWuP7GPf98-mqo-n4FV37SkgeTO6hylvnQovqIcpxF_Kty0PaaFRQ'
        self.headers = self._get_auth_headers()

    def _get_auth_headers(self):
        headers = {'Authorization': 'Bearer %s' % self.developer_token}
        if self.user_access_token:
            headers['Music-User-Token'] = self.user_access_token
        return headers


    def _request_method(self, method):
        return {
            'GET': requests.get,
            'POST': requests.post,
            'PUT': requests.put,
            'PATCH': requests.patch,
            'DELETE': requests.delete,
        }.get(method)

    def _make_request(self, method, endpoint, base_path=None, params=None,
                      payload=None):
        if base_path is None:
            base_path = "/%s" % self.api_version
        params = params or {}
        payload = payload or {}
        url = "%s%s%s" % (self.base_url, base_path, endpoint)
        request_method = self._request_method(method)
        for _ in range(12):
            try:
                response = request_method(url,
                                        params=params,
                                        headers=self.headers,
                                        data=json.dumps(payload),
                                        timeout=self.timeout,
                                        stream = True)
            except:
                pass
            else:
                break
        
        response.raise_for_status()
        return response.content and response.json() or {}

    """Helper Functions"""

    @property
    def access_token(self):
        return self.user_access_token

    @access_token.setter
    def access_token(self, value):
        self.headers['Music-User-Token'] = self.user_access_token = value

    def refresh_developer_token(self):
        self.headers = self._get_auth_headers()

    def next(self, resource, limit=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/RelationshipsandPagination.html#//apple_ref/doc/uid/TP40017625-CH135-SW1
        """
        if not (resource and resource.get('next')):
            return None
        params = {}
        if limit:
            params['limit'] = limit
        return self._make_request(
            method='GET',
            endpoint=resource.get('next'),
            base_path='',
            params=params,
        )

    def _build_track(self, track_id, track_type=TRACK_TYPE_SONGS):
        """https://developer.apple.com/documentation/applemusicapi/libraryplaylistrequesttrack
        """
        return {
            'id': str(track_id),
            'type': TRACK_TYPE_SONGS,
        }

    def _build_tracks(self, track_ids, track_type=TRACK_TYPE_SONGS):
        """
        TODO: Offer the ability to add dynamic track types per track id
        """
        return list(map(lambda track_id: self._build_track(track_id, track_type),
                   track_ids))

    """API Endpoints"""

    def search(self, query, limit=None, offset=None, storefront='us',
               types=TRACK_TYPE_SONGS):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/Searchforresources.html#//apple_ref/doc/uid/TP40017625-CH58-SW1
        """
        if not query:
            return
        params = {'term': query}
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        if types:
            params['types'] = types
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/search" % storefront,
            params=params,
        )

    def get_song(self, id, storefront='us', include=None):
        """https://developer.apple.com/documentation/applemusicapi/get_a_catalog_song
        """
        params = {}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/songs/%s" % (storefront, id),
            params=params,
        )

    def get_songs(self, ids, storefront='us', include=None):
        """https://developer.apple.com/documentation/applemusicapi/get_multiple_catalog_songs_by_id
        """
        params = {'ids': ','.join(ids)}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/songs" % storefront,
            params=params,
        )

    def get_songs_by_isrc(self, isrc, storefront='us', include=None):
        """https://developer.apple.com/documentation/applemusicapi/get_multiple_catalog_songs_by_isrc
        """
        params = {'filter[isrc]': isrc}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/songs" % storefront,
            params=params,
        )

    def get_playlist(self, id, storefront='us', include=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/GetaSinglePlaylist.html#//apple_ref/doc/uid/TP40017625-CH20-SW1
        """
        params = {}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/playlists/%s" % (storefront, id),
            params=params,
        )

    def get_playlists(self, ids, storefront='us', include=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/GetMultiplePlaylists.html#//apple_ref/doc/uid/TP40017625-CH21-SW1
        """
        params = {'ids': ','.join(ids)}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/playlists" % storefront,
            params=params,
        )

    def get_genre(self, id, storefront='us', include=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/GetaSingleGenres.html#//apple_ref/doc/uid/TP40017625-CH16-SW1
        """
        params = {}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/genres/%s" % (storefront, id),
            params=params,
        )

    def get_genres(self, ids, storefront='us', include=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/GetMultipleGenres.html#//apple_ref/doc/uid/TP40017625-CH17-SW1
        """
        params = {'ids': ','.join(ids)}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/catalog/%s/genres" % storefront,
            params=params,
        )

    def user_playlist_create(self, name, description=None, track_ids=None,
                             include=None):
        """
        Params:
            `name` <str>
            `description` <str>
            `track_ids` <list(<str>, ...)>
            # TODO: Example(s) of `include`?
            `include` <str> Additional relationships to include in the fetch.

        https://developer.apple.com/documentation/applemusicapi/create_a_new_library_playlist

        Note: As of now (2018-07-27), adding tracks in this request fails with
        a 400 error. YMMV.
        """
        params = None
        # https://developer.apple.com/documentation/applemusicapi/libraryplaylistcreationrequest
        # https://developer.apple.com/documentation/applemusicapi/libraryplaylistcreationrequest/attributes
        payload = {'attributes': {'name': name}}
        if description:
            payload['attributes']['description'] = description
        if track_ids:
            # https://developer.apple.com/documentation/applemusicapi/libraryplaylistcreationrequest/relationships
            # https://developer.apple.com/documentation/applemusicapi/libraryplaylistrequesttrack
            tracks = self._build_tracks(track_ids)
            payload['relationships'] = {'tracks': tracks}
        if include:
            params = {'include': include}
        return self._make_request(
            method='POST',
            endpoint='/me/library/playlists',
            params=params,
            payload=payload,
        )

    # As of 2018-08-06 this endpoint is no longer documented and attempts to
    # reach it return a `501`, which according to the error codes docs suggests
    # "Endpoint is currently unavailable and reserved for future use."
    # def user_playlist_update(self, id, name=None, description=None):
    #     payload = {'attributes': {}}
    #     if name:
    #         payload['attributes']['name'] = name
    #     if description:
    #         payload['attributes']['description'] = description
    #     return self._make_request(
    #         method='PATCH',
    #         endpoint="/me/library/playlists/%s" % id,
    #         payload=payload,
    #     )

    # As of 2018-07-27 this endpoint is no longer documented and attempts to
    # reach it return a `403`
    # def user_playlist_delete(self, id):
    #     return self._make_request(
    #         method='DELETE',
    #         endpoint="/me/library/playlists/%s" % id,
    #     )

    def user_playlist_add_tracks(self, id, track_ids):
        """https://developer.apple.com/documentation/applemusicapi/add_tracks_to_library_playlist
        """

        tracks = self._build_tracks(track_ids)
        payload = {'data': tracks}
        return self._make_request(
            method='POST',
            endpoint="/me/library/playlists/%s/tracks" % id,
            payload=payload,
        )

    # As of 2018-07-27 this endpoint is no longer documented and attempts to
    # reach it return a `403`
    # def user_playlist_replace_tracks(self, id, track_ids):
    #     tracks = self._build_tracks(track_ids)
    #     payload = {'data': tracks}
    #     return self._make_request(
    #         method='PUT',
    #         endpoint="/me/library/playlists/%s/tracks" % id,
    #         payload=payload,
    #     )

    def user_playlist_remove_tracks(self, id, track_ids):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/DeleteTrackfromLibraryPlaylist.html#//apple_ref/doc/uid/TP40017625-CH251-SW1
        """
        params = {
            'ids[library-songs]': [str(track_id) for track_id in track_ids],
            'mode': 'all',
        }
        return self._make_request(
            method='DELETE',
            endpoint="/me/library/playlists/%s" % id,
            params=params,
        )

    def user_playlist(self, id, include=None):
        """https://developer.apple.com/documentation/applemusicapi/get_a_library_playlist
        """
        params = {}
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint="/me/library/playlists/%s" % id,
            params=params,
        )

    def user_playlists(self, limit=None, offset=None, include=None):
        """https://developer.apple.com/documentation/applemusicapi/get_all_library_playlists

        Params:
            `include` [string]
                Additional relationships to include in the fetch.
            `l` string
                The localization to use, specified by a language tag. The
                possible values are in the supportedLanguageTags array belonging
                to the Storefront object specified by storefront. Otherwise, the
                storefront’s defaultLanguageTag is used.
            `limit` number
                The limit on the number of objects, or number of objects in the
                specified relationship, that are returned. The default value is
                25 and the maximum value is 100.
            `offset` string
                The next page or group of objects to fetch.
        """
        params = {}
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint='/me/library/playlists',
            params=params,
        )

    def user_heavy_rotation(self, limit=None, offset=None):
        """https://developer.apple.com/documentation/applemusicapi/get_heavy_rotation_content
        """
        params = {}
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        return self._make_request(
            method='GET',
            endpoint='/me/history/heavy-rotation',
            params=params,
        )

    def user_recent_played(self, limit=None, offset=None):
        """https://developer.apple.com/documentation/applemusicapi/get_recently_played

        As of 2018-08-06, it seems the limit per request is 10 songs. Requesting
        any more will lead to a `400` response error.

        The response contains a list of dictionaries describing the tracks
        listened to.

        As far as contextual data, the timestamp of when the listen occured
        is not included, but a dictionary of `playParams` does offer some
        information. Example:

            u'playParams': {u'id': u'298992486', u'kind': u'album'}
        """
        params = {}
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        return self._make_request(
            method='GET',
            endpoint='/me/recent/played',
            params=params,
        )

    def user_recent_added(self, limit=None, offset=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/GetRecentlyAdded.html#//apple_ref/doc/uid/TP40017625-CH226-SW1
        """
        params = {}
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        return self._make_request(
            method='GET',
            endpoint='/me/library/recently-added',
            params=params,
        )

    def user_songs(self, limit=None, include=None):
        """https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/GetAllLibrarySongs.html#//apple_ref/doc/uid/TP40017625-CH217-SW1
        """
        params = {}
        if limit:
            params['limit'] = limit
        if include:
            params['include'] = include
        return self._make_request(
            method='GET',
            endpoint='/me/library/songs',
            params=params,
        )

    def test(self):
        """
        https://api.music.apple.com/v1/test
        https://developer.apple.com/documentation/applemusicapi/getting_keys_and_creating_tokens
        """
        return self._make_request(method='GET', endpoint='/test')
