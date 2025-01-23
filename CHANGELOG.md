# Changelog

Here, the changes to `SpaceTraders v2` will be summarized.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

### Changed

### Removed

### Fixed


## [0.2] - e98b03c

The aim for this stage was to collect data from MARKETPLACEs and SHIPYARDs in start systems.
Many steps were required in order to do this: ship and system classes, basic ship pathing, and a distributed task system to automate ships.


### Added
  - `spies` module:
    - `spymaster` uses the `cartographer`'s output to identify start systems, 
    and inserts probes into every market
  - `systems` module and class
  - `agent` module:
    - `register_agent` and `register_random_agent` functions
  - `ship` module and class
  - `pathing` module:
    - `travel` function for fire-and-forget navigate from origin to destination
    - rudimentary `get_path` function for navigation between fuel stops
  - `ai` module
    - `taskMaster` class that can manage automated scripts in a separate process
    - `ai_probe_waypoint` task to send a probe to a waypoint and update the DB
    - `ai_seed_system` task to buy probes and assign them a waypoint

### Changed
  - integrated more classes with the DB
    - registering an agent now also inserts ships and contracts into the DB

### Removed
  - several intermediate DB tables

### Fixed
  - PSQL database now uses case-sensitive columns identical to the game


## [0.1] - 5616f8f

To goal is to create a visualization of the game universe with rich data elements.

The aim for this stage was to implement a fast, thread-safe database.
This is used to store the systems and waypoints, which are collected by the `stargazers`.

Another aim was to implement a framework for a multiprocessed script.
This is used to centralize the API requests (to control the rate limit),
and to enable more heavy computations.


### Added
  - implemented a PostgreSQL database with psycopg3
  - `request` module:
    - `Request` handles API requests
    - `RequestMP` handles API requests in a multiprocess context, via the `messenger`
    - `messenger` delivers API requests between `Request` and `RequestMp` instances
  - `startup` module functions for the main thread: 
    - checks the current game state (for server resets)
    - starts the database server
    - starts the API process
  - `agent` module:
    - `api_agent` creates a single random agent for use in background API requests
      - this agent will 'notify' the script when the server resets
  - `stargazers` module:
    - `astronomer` charts all systems in the background
    - `cartographer` charts all waypoints in the background
      - maps the start systems & gate systems
