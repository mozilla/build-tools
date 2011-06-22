-- use these to set up the db before the first run.  These statements
-- are designed for SQLite; for MySQL, use AUTO_INCREMENT instead.

CREATE TABLE builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master VARCHAR(100),
    branch VARCHAR(50),
    buildername VARCHAR(100),
    builddir VARCHAR(100),
    slave VARCHAR(30),
    last_build_time INTEGER);

CREATE TABLE clobber_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master VARCHAR(100),
    branch VARCHAR(50),
    builddir VARCHAR(100),
    slave VARCHAR(30),
    lastclobber INTEGER,
    who VARCHAR(50));

