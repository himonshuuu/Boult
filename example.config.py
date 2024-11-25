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



class bot:
    token = "YOUR_BOT_TOKEN_HERE"
    canary_token = "YOUR_TEST_BOT_TOKEN_HERE"
    default_prefix = "b?"
    canary_prefix = "b"
    extensions = ["cogs.music", "cogs.meta", "cogs.events", "cogs.utility"]
    
    support_invite = "YOUR_DISCORD_INVITE_LINK"
    
    statuses = [{"watching": "boult beats"}, {"listening": ""}]

class color:
    color = 0x2B2D31
    error_color = 0xFF0000
    success_color = 0x00FF00

class pgsql:
    pg_user = "your_postgres_user"
    pg_host = "your_host"
    pg_port = "5432"
    pg_dbname = "your_database_name"
    pg_auth = "your_password"
    pg_dsn = "postgresql://user:password@host:5432/dbname"

class mongodb:
    uri = "mongodb+srv://username:password@your-cluster-url"

class channels:
    join_log = 123456789  # Channel ID for join logs
    leave_log = 123456789  # Channel ID for leave logs

class lavalink:
    nodes = [
        {"host": "your.lavalink.host", "port": "3000", "auth": "your_password"},
    ]

class api_keys:
    spotify_client_id = "your_spotify_client_id"
    spotify_client_secret = "your_spotify_client_secret"

class emoji:
    play = "<:play:1229722309582127135>"
    stop = "<:music_stop:1229727886290976770>"
    pause = "<:pause:1229726832329363498>"
    next = "<:next:1229723598013595659>"
    prev = "<:previous:1229723220488224769>"
    lyrics = "<:lyrics:1229735064552603648>"
    queue = "<:playlist_avon:1229721986674983043>"
    loop = "<:Loop:1229730194861064194>"
    trash = "<:trash:1172606399595937913>"
    filter = "<:filter:1229734301608706049>"
    lyrics2 = "<:lyrics22:1229719517370777681>"
    deezer = "<:Deezer:1220248030201118740>"
    spotify = "<:spotify:1220247976354779156>"
    soundcloud = "<:soundcloud:1220248137268990063>"
    youtube = "<:youtube:1220247238169595924>"
    add = "<:plus:1172608535050338434>"
    bookmark = "<:Favorito:1229724301847171123>"
    nping = "<:Good:1246824514994835507>"
    mping = "<:Idle_network:1246824743315836991>"
    bping = "<:bad_network:1246824491665850388>"
    discord = "<:Discord:1299392149384859710>"
    postgresql = "<:postgresql:1299392496069120061>"
    voice = "<:voice:1299392295816265874>"
    volup = "<:Volume_up:1299724881654448179>"
    voldown = "<:LowVolume:1299725017206231040>"
    upload = "<:Upload:1299752378999902278>"
    download = "<:download:1299752375417835552>"
    loop_track = "<:t_loop1:1299819953649745942>"
    loop_queue = "<:icon_loop:1299820129403670568>"
    search = "<:search:1305502599977373717>"
    jiosaavn = "<:jiosaavn:1305942405849288855>"
    icon1 = "<:icons_text1:1308440950028111944>"
    icon2 = "<:icons_text2:1308440966507790356>"
    icon3 = "<:icons_text3:1308450520867934318>"
    icon4 = "<:icons_text4:1308450532817506406>"
    icon6 = "<:icons_text6:1308453644844142692>"
    null = "<:EmptySpace:1308800454234341386>"

class badges:
    bot = "<:bot:1257989216516837408>"
    user = "<:user:1259523635157405867>"
    developer = "<:Developer:1259523524096299113>"
    helpers = "<:helpers:1259523900677820527>"
    bug_hunter = "<:BugHunter:1259523757098405940>"
    owner = "<:owner:1259524030868885557>"
    manager = "<:utility:1257989664418168932>"
    activedeveloper = "<:developeractivo:1259523547416494190>"