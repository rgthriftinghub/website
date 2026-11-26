BEGIN;

-- Running upgrade a19f6b3d8c42 -> d3f7a91c6b42

ALTER TABLE products ALTER COLUMN short_description TYPE TEXT USING short_description::text;

ALTER TABLE products ALTER COLUMN meta_description TYPE TEXT USING meta_description::text;

UPDATE alembic_version SET version_num='d3f7a91c6b42' WHERE alembic_version.version_num = 'a19f6b3d8c42';

COMMIT;

