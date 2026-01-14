# CHANGELOG


## v0.1.3 (2026-01-14)

### Chores

- Update volume permissions
  ([`ebc07d3`](https://github.com/timmyb824/server-monitoring-made-easy/commit/ebc07d3de5f5e08ff87668657cef8a57732d9451))


## v0.1.2 (2025-01-29)

### Bug Fixes

- Fix handling of file path expansion and directory creation in FileAlertStorage
  ([`6ce4f5d`](https://github.com/timmyb824/server-monitoring-made-easy/commit/6ce4f5dbbd9d4410b966db3343c4e1f54c4bcacb))

- Issue preventing package from being built; added tools.poetry section back as its still supported;
  fixed dynamic versioning.
  ([`d0bce88`](https://github.com/timmyb824/server-monitoring-made-easy/commit/d0bce88d048703cc8bb55e375e06d8f0b918e861))

- Remove telegram hardcode and allow any notification type
  ([`acbca14`](https://github.com/timmyb824/server-monitoring-made-easy/commit/acbca143830d7194470d827382ceb066b752197b))

- Update dependencies to use Poetry 2.0.0 and Python 3.9 as required-python
  ([`814f488`](https://github.com/timmyb824/server-monitoring-made-easy/commit/814f488efc0d869eb4215932774652c02202232e))

- Update poetry version to 2.0.0
  ([`f3deae2`](https://github.com/timmyb824/server-monitoring-made-easy/commit/f3deae2669a072901be9217819c6b3c802ed2d32))


## v0.1.1 (2024-12-19)

### Documentation

- Update readme to relect current state
  ([`3774547`](https://github.com/timmyb824/server-monitoring-made-easy/commit/3774547b97688f0e9115050804d13a26dea2e65f))

### Refactoring

- Expand all path values in the configuration before merging them with the loaded file config
  ([`d315ecc`](https://github.com/timmyb824/server-monitoring-made-easy/commit/d315ecc72268aace7972b31bbe5601edde8a8432))


## v0.1.0 (2024-12-19)

### Bug Fixes

- Update logging configuration to set default levels and configure logging based on loaded config
  ([`6417555`](https://github.com/timmyb824/server-monitoring-made-easy/commit/6417555cfad7ecf7a3c284a983738cf0f3baeb82))

### Code Style

- Improve setup.sh formatting and command suggestion
  ([`d69ebe1`](https://github.com/timmyb824/server-monitoring-made-easy/commit/d69ebe1306f57cba0851955569537729dd5a4421))

### Continuous Integration

- Add workflow file to publish to pypi
  ([`3bb4bbc`](https://github.com/timmyb824/server-monitoring-made-easy/commit/3bb4bbc06227f9ae27b6e33069d0308428061992))

- Pre-commit changes
  ([`112c330`](https://github.com/timmyb824/server-monitoring-made-easy/commit/112c330a63f864f571e86d722acc2adeb49c63cf))

### Documentation

- Add MIT license
  ([`9ac69fd`](https://github.com/timmyb824/server-monitoring-made-easy/commit/9ac69fd3aad74ff4b397ce89569935bad42c14d2))

- Update .gitignore and remove config.yaml
  ([`605a2a0`](https://github.com/timmyb824/server-monitoring-made-easy/commit/605a2a0139a923fcc07d45081d324621fc7b5357))

### Features

- Add asynchronous notification sending functionality with Apprise integration
  ([`53cc568`](https://github.com/timmyb824/server-monitoring-made-easy/commit/53cc5687807c7bc11e3cd832fdd563d554b65371))

- Add function to initialize a new configuration file with default settings
  ([`fcda1d7`](https://github.com/timmyb824/server-monitoring-made-easy/commit/fcda1d7101b2ca3307fffa885bac0f797d982660))

- Add metrics command to display system metrics and network latency
  ([`9b0a0cc`](https://github.com/timmyb824/server-monitoring-made-easy/commit/9b0a0ccf7211394104490b781aaa32d625aa278d))

- Add multi-stage build for Dockerfile, improve Docker-compose compatibility
  ([`dc9447e`](https://github.com/timmyb824/server-monitoring-made-easy/commit/dc9447e29ca359238608dda311ec168a277988d9))

- Add pre-commit and pylint configs
  ([`89b8187`](https://github.com/timmyb824/server-monitoring-made-easy/commit/89b818757226333c932f88800cc1fe74b9b680fb))

- Add server monitoring configuration in config_example.yaml
  ([`92f47de`](https://github.com/timmyb824/server-monitoring-made-easy/commit/92f47de6976f9993df81dbc0e847131e1900a0e9))

- Add version command
  ([`dc00de6`](https://github.com/timmyb824/server-monitoring-made-easy/commit/dc00de64a83cb214407d8307a991e162f66e7ad1))

- Enhance setup_logging function and add component-specific log levels
  ([`695a4ee`](https://github.com/timmyb824/server-monitoring-made-easy/commit/695a4eebe96cd3795484bac53259b585790be3a8))

- Enhance user/group ID handling in docker-compose and set up script
  ([`b638fe1`](https://github.com/timmyb824/server-monitoring-made-easy/commit/b638fe1ccb701ccc5e8ff29c52fa6dc7c4f0d098))

- Implement file storage so alerts can persist; implement skeleton of postgres storage with alembic
  ([`05923ff`](https://github.com/timmyb824/server-monitoring-made-easy/commit/05923ff28096bdfc7f936c4689548cf258ea3062))

- Implement postgres storage successfully by cleaning up database connection handling and
  initialization logic
  ([`660369a`](https://github.com/timmyb824/server-monitoring-made-easy/commit/660369a3c727ed5755efd7811597412ed484512b))

### Refactoring

- Fix import paths and refactor AlertManager class for better error handling and logging
  ([`4a344fc`](https://github.com/timmyb824/server-monitoring-made-easy/commit/4a344fcc98ef442a7c3ae82d87e98fdc95c9a385))

- Handle None config by setting it to an empty dictionary
  ([`2bb15ac`](https://github.com/timmyb824/server-monitoring-made-easy/commit/2bb15ac6135cfe15587e8c757dd616e829724d96))

- Improve monitor initialization and logging configuration
  ([`ba71204`](https://github.com/timmyb824/server-monitoring-made-easy/commit/ba7120403734a8a40206c36255c448fc9e786f40))

- Update Dockerfile to improve image size and setup.sh for directory permissions
  ([`223bc91`](https://github.com/timmyb824/server-monitoring-made-easy/commit/223bc91776e6b144fc210de72719e4e580c49e45))

- Update log level from debug to info for successful notification service addition
  ([`a99586e`](https://github.com/timmyb824/server-monitoring-made-easy/commit/a99586e8233fed607bcae90d9bb46b4f4af5b2f7))

- Update method name from handle_alert to process_alert in app/cli.py
  ([`2b6b382`](https://github.com/timmyb824/server-monitoring-made-easy/commit/2b6b3825ada2f56b98a2cfd339cba785fd3c620a))

### Testing

- Add basic testing to be used in the ci workflow
  ([`ca50e02`](https://github.com/timmyb824/server-monitoring-made-easy/commit/ca50e02b8bc151e645f855f7f2aa9a40733b78ae))
