## Unit tests for PeARS-OMD

### Prerequisites

* You should have a running installation of PeARS-OMD with an existing index. We recommend to run tests in a separate directory from your main PeARS-OMD install, as the tests will directly interact with your database. The easiest way to do this is to duplicate your installation and use the copy to run tests.

* Fill in the config file for the test suite. A template is available here. You should copy and fill it in.

```
cd conf
cp test.pears.ini.template test.pears.ini
```

Open the *test.pears.ini* file and fill it in. The TEST\_XML\_URL variable should be set to one of your personal OMD folder. You can pick one path from your 'profile' page in the app, preferably one does not contain many files, to avoid having lengthy tests. The test username, password and device fields should be set to your On My Disk credentials and the name of the device you are using for testing. (This will be the part after your username in the TEST\_XML\_URL variable.)

### Run the tests

Run with 

```
pytest --disable-warnings
```
