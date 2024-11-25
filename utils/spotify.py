""" 
MIT License

Copyright (c) 2024 Himangshu Saikia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""



import os
from spotipy import SpotifyClientCredentials
import spotipy
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
import aiohttp
import asyncio


class SpotifyEntity:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    def __repr__(self):
        return f"SpotifyEntity(name={self.name}, url={self.url})"


class SpotifyArtistReference:
    def __init__(self, data: Dict[str, Any]):
        self.entity = SpotifyEntity(
            data.get("name", ""), data.get("external_urls", {}).get("spotify", "")
        )
        self.genres = data.get("genres", [])

    def __repr__(self):
        return f"SpotifyArtistReference(name={self.entity.name}, url={self.entity.url}, genres={self.genres})"


class SpotifyTrack:
    def __init__(self, data: Dict[str, Any]):
        if isinstance(data, dict):
            self.entity = SpotifyEntity(
                data.get("name", ""), data.get("external_urls", {}).get("spotify", "")
            )
            self.duration_ms = data.get("duration_ms", 0)
            self.artists = [
                SpotifyArtistReference(artist) for artist in data.get("artists", [])
            ]
            self.artwork = (
                data.get("images", [{}])[0].get("url") if data.get("images") else None
            )
            self.preview_url = data.get("preview_url")
            self.popularity = data.get("popularity", 0)
        else:
            raise ValueError(
                f"Expected dictionary for track data, but got {type(data)}: {data}"
            )

    def __repr__(self):
        return f"SpotifyTrack(name={self.entity.name}, url={self.entity.url}, popularity={self.popularity})"


class SpotifyPlaylist:
    def __init__(self, data: Dict[str, Any], tracks: List[Dict[str, Any]]):
        self.entity = SpotifyEntity(
            data.get("name", ""), data.get("external_urls", {}).get("spotify", "")
        )
        self.tracks = []
        self.artwork = (
            data.get("images", [{}])[0].get("url") if data.get("images") else None
        )
        for track in tracks:
            try:
                self.tracks.append(SpotifyTrack(track.get("track", {})))
            except ValueError as e:
                pass

    def __repr__(self):
        return (
            f"SpotifyPlaylist(name={self.entity.name}, tracks_count={len(self.tracks)})"
        )


class SpotifyAlbum:
    def __init__(self, data: Dict[str, Any], tracks: List[Dict[str, Any]]):
        self.entity = SpotifyEntity(
            data.get("name", ""), data.get("external_urls", {}).get("spotify", "")
        )
        self.tracks = [
            SpotifyTrack(track) for track in tracks if isinstance(track, dict)
        ]
        self.release_date = data.get("release_date", "")
        self.artwork = (
            data.get("images", [{}])[0].get("url") if data.get("images") else None
        )

    def __repr__(self):
        return f"SpotifyAlbum(name={self.entity.name}, release_date={self.release_date}, tracks_count={len(self.tracks)})"


class SpotifyArtist:
    def __init__(self, data: Dict[str, Any], tracks: List[Dict[str, Any]]):
        self.entity = SpotifyEntity(
            data.get("name", ""), data.get("external_urls", {}).get("spotify", "")
        )
        self.artwork = (
            data.get("images", [{}])[0].get("url") if data.get("images") else None
        )
        self.top_tracks = [SpotifyTrack(track) for track in tracks]
        self.genres = data.get("genres", [])

    def __repr__(self):
        return f"SpotifyArtist(name={self.entity.name}, genres={self.genres}, top_tracks_count={len(self.top_tracks)})"


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str):
        self._auth_manager = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        self._spotify = spotipy.Spotify(auth_manager=self._auth_manager)

    async def get_thumbnail(self, identifier: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://embed.spotify.com/oembed/?url=spotify:track:{identifier}"
            ) as r:
                return (await r.json())["thumbnail_url"]

    async def search_tracks(
        self, query: str, limit: int = 5, market: str = "IN"
    ) -> List[SpotifyTrack]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, lambda: self._spotify.search(q=query, limit=limit, market=market)
        )
        return [SpotifyTrack(track) for track in results["tracks"]["items"]]

    async def get_track(self, track_id: str) -> Optional["SpotifyTrack"]:
        try:
            loop = asyncio.get_event_loop()
            track_data = await loop.run_in_executor(
                None, lambda: self._spotify.track(track_id)
            )
            return SpotifyTrack(track_data)
        except spotipy.exceptions.SpotifyException as e:
            return None

    async def get_playlist(self, url: str) -> Optional["SpotifyPlaylist"]:
        playlist_id = self._extract_id(url)
        loop = asyncio.get_event_loop()
        playlist_data = await loop.run_in_executor(
            None,
            lambda: self._spotify.playlist(
                playlist_id, fields="name,external_urls,images"
            ),
        )
        playlist_tracks = await loop.run_in_executor(
            None, lambda: self._spotify.playlist_tracks(playlist_id, market="IN")
        )

        if not playlist_tracks["items"]:
            return None

        tracks = [item for item in playlist_tracks["items"]]
        return SpotifyPlaylist(playlist_data, tracks)

    async def get_album(self, url: str) -> Optional["SpotifyAlbum"]:
        album_id = self._extract_id(url)
        loop = asyncio.get_event_loop()
        album_data = await loop.run_in_executor(
            None, lambda: self._spotify.album(album_id)
        )
        album_tracks = await loop.run_in_executor(
            None, lambda: self._spotify.album_tracks(album_id)
        )
        if not album_tracks["items"]:
            return None

        return SpotifyAlbum(album_data, album_tracks)

    async def get_artist(self, url: str) -> Optional["SpotifyArtist"]:
        artist_id = self._extract_id(url)
        loop = asyncio.get_event_loop()
        artist_data = await loop.run_in_executor(
            None, lambda: self._spotify.artist(artist_id)
        )
        top_tracks = await loop.run_in_executor(
            None, lambda: self._spotify.artist_top_tracks(artist_id)
        )

        if not top_tracks["tracks"]:
            return None

        return SpotifyArtist(artist_data, top_tracks["tracks"])

    @staticmethod
    def _extract_id(spotify_url: str) -> str:
        parsed_url = urlparse(spotify_url)
        path_segments = parsed_url.path.split("/")
        return path_segments[2] if len(path_segments) >= 3 else None
