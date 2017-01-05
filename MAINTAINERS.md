# Maintainers

This document contains the instructions related to pull request and merge
management activities.

## Pull Request Management

When a Pull Request (PR) passes CI tests and the community successfully
resolved any issues raised during the peer review of the PR, the PR is
ready for a merger.

## Release Management

A maintainer SHOULD create a Pull Request for cutting a release. Consequently,
a part of the work on release management happens on in a forked branch, and
the other part in the main repository.

Before cutting a release, the maintainer MUST validate that she or he has
`pandoc` and `Sphinx` installed.

```
sudo yum -y install pandoc
sudo pip install Sphinx
```

### Forked Branch

First, the maintainer MUST change the value of the `PLUGIN_VER` in
`Makefile`, because the variable is used to change version references
across the entire project, e.g. CI and Dockerfile references.

```
PLUGIN_VER=0.7
```

After that, the maintainer runs `make` to update version references and
create new documentation.:

```
make package
```

Then, the maintainer creates a PR.

### Main Repository.

The work on release management happens on the main repository, not its fork.

A maintainer should have the following information before cutting a release:
- New release version
- Release name

Next, the maintainer tags the release with an appropriate version and name.
The maintainer pushes the tags to upstream.

```
git tag -a v0.7 -m "Flamingo Release"
git push
git push --tags
```

Next, the maintainer should upload the new release to PyPi:

```
python setup.py sdist upload -r pypitest
```

Then, the maintainer should review the project's
[Test PyPi](https://testpypi.python.org/pypi/ansible-plugin-clicap/) page.

Once the maintainer validated that Test PyPi looks as expected, the maintainer
pushes the code to the main PyPi repository.

```
python setup.py sdist upload -r pypi
```

