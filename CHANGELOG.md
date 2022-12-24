# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## Unreleased

The roadmap will be posted here [Project](https://github.com/plynx-team/plynx/projects).

Please join the discussions in the [Discord](https://discord.gg/ZC3wY2J).

### Recent releases

## [1.9.8] - 2022-12-24

- Parse file extensions in upload dialog to determine the right type.
- Fix redirection logic.

## [1.9.7] - 2022-12-23

- Add ability to upload a file in Workflow editor.

## [1.9.4] - 2022-12-22

- Using Oauth2 to sign-up / log-in.
- Isolate workers from using database directly.

## [1.9.3] - 2022-12-11

- Fix a bug: do not restart a failed Operation without explicit action.
- Indicate running Operations using styles.

## [1.9.2] - 2022-12-10

- Some of the Operations have auto-run disabled.
- Auto-run can be specified on Operations level.
- Improved sync with a running job: it is not restarted with minor changes.

## [1.9.1] - 2022-11-26

- UI fixes.
- MongoDB: allow using disk in aggregation.

## [1.9.0] - 2022-11-25

- Updated react version to 17.
- Using reactFlow as the workflow engine.
- Added interactive Operation lookup.

## [1.8.1] - 2022-10-19

- Using single threaded python DAG by default.
- UI bug fixes.

## [1.8.0] - 2022-10-17

- Auto-sync and auto-run flags for interactive DAGs.
- Interactive DAG editor: subnode status is updated in the edit mode.
- UI: using only kind-title in the nodes.

## [1.7.9] - 2022-04-19

- Local DAG executor now supports Operations defined in the DB.

## [1.7.8] - 2022-04-18

- Refactoring: DB structure relies on python type annotation.
- Using python linters.
- Updated documentation and cleaned up the code.

## [1.7.5] - 2022-02-13

- New python API to create operations from the code.
- Improved Static List Hub with the support of Python API.
- Support of folders in the hubs.
- New local DAG executor.
