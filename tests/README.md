## Unit tests for PeARS-OMD

### Prerequisites

* You should have a running installation of PeARS-OMD with an existing index. Please refer to the [general installation instructions](https://github.com/PeARSearch/PeARS-OMD) to set up your app. We recommend to run tests in a separate directory from your main PeARS-OMD install, as the tests will directly interact with your database. The easiest way to do this is to duplicate your installation and use the copy to run your tests. For instance:

```
OnMyDisk
|__ PeARS-OMD (your general install)
|__ PeARS-OMD-dev (your install for development and test purposes)
```

* Fill in the config file for the test suite. A template is available from the *conf/* directory. You should copy and fill it in.

```
cd conf
cp test.pears.ini.template test.pears.ini
```

Open the *test.pears.ini* file and fill it in. The TEST\_XML\_URL variable should be set to one of your personal OMD folder. You can pick one path from your 'profile' page in the app, preferably one does not contain many files, to avoid having lengthy tests. The test username, password and device fields should be set to your On My Disk credentials and the name of the device you are using for testing. (This will be the part after your username in the TEST\_XML\_URL variable.)


### Backing up

It is convenient to have a backup of your database and search indices when running tests. If something goes wrong, you can easily restore the previous state of your installation before running further tests.

You should generate your backup from the root directory of your PeARS-OMD installation. Run:

```
flask pears backup
```

This will create a snapshot of your personal index files in the .backups folder. You can inspect the content of that folder, which should show you timestamped directories. For instance:

```
ls .backups/
>> pears-2025-05-15-12h25m
```

If you ever need to restore your files from a particular snapshot, run the following, using the correct directory name. For example:

```
flask pears restore pears-2025-05-15-12h25m
```

### Run the tests

| :point_up:    | Check before testing |
|:-------------------------------------|
| Ensure that you are not running the front end while also running your tests. There could be interactions with calls from the On My Disk gateway that spuriously affect the test results. |

Run the tests with:

```
pytest --disable-warnings
```
