CREATE TABLE user_play_data (
    user_id BIGINT NOT NULL,
    track_id VARCHAR(255) NOT NULL,
    plays INTEGER DEFAULT 1,
    duration INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, track_id)
);

CREATE TABLE test(
    id SERIAL NOT NULL,
    test text NOT NULL,
    PRIMARY KEY(id)
);

CREATE TABLE dj_config(
    guild_id bigint NOT NULL,
    role_id bigint,
    PRIMARY KEY(guild_id)
);

CREATE TABLE user_config(
    user_id bigint NOT NULL,
    search_engine text,
    no_prefix boolean,
    PRIMARY KEY(user_id)
);


-- NOT IMPLEMENTED YET 
-- MAYBE IN FUTURE
-- YOU CAN ALSO CONTRIBUTE TO THIS IF YOU WANT
CREATE TABLE user_playlists (
    user_id BIGINT NOT NULL,
    playlist_id BIGINT NOT NULL REFERENCES playlist(playlist_id) ON DELETE CASCADE
);

CREATE TABLE playlist (
    playlist_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tracks JSONB NOT NULL
);


CREATE TABLE guild_config (
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(255) DEFAULT "b?"
);