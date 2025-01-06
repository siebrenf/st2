# Changelog

Here, the changes to `SpaceTraders v2` will be summarized.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
  - logging with Loguru
  - caching with Diskcache
  - database with PostgreSQL & psycopg3
  - `request` module:
    - `Request` handles API requests
    - `RequestMP` handles API requests in a multiprocess context, via the `messenger`.
    - `messenger` delivers API requests between `Request` and `RequestMp` instances.
  - `startup` module functions for the main thread: 
    - checks the current game state (for server resets)
    - starts the database server
    - starts the API process
  - `agent` module:
    - `api_agent` creates a single random agent for use in background API requests.
      - this agent will 'notify' the script when the server resets.
  - `stargazers` module:
    - `astronomer` charts all systems in the background
    - `cartographer` charts all waypoints in the background
      - maps the start systems & gate systems

### Changed

### Removed

### Fixed
