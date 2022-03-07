.. _contributing:

Contributing
------------

Thank you for considering contributing to WATTS! We look forward to any
contributions from the community.

General Rules
+++++++++++++

All changes to WATTS are made via pull request to the GitHub repository. Every
pull request must be independently reviewed and approved by a member of the
WATTS core development team before it may be merged.

Development Workflow
++++++++++++++++++++

Making a contribution to WATTS works as follows:

1. Get a local copy of the repository:

    - Go to https://github.com/watts-dev/watts and click the "fork" button to
      create a copy of the project.

    - Clone the repository::

        git clone https://github.com/<username>/watts.git

    - Go into the new repository::

        cd watts

2. Make your contribution:

    - Create a new branch to work on with a short name that roughly describes
      what you're implementing. For example, if you want a branch called
      ``new-plugin``::

        git checkout -b new-plugin

    - Commit your changes to the branch::

        git add <file 1> <file 2> ...
        git commit -m "Commit message"

3. Submit your contribution for review:

    - Make sure you've covered all the points on the contribution :ref:`checklist
      <checklist>` before proceeding.

    - Push your local branch to your fork (which by default is the remote called
      ``origin``)::

        git push origin new-plugin

    - Go to https://github.com/watts-dev/watt and create a new pull request.
      Select your fork as the "head repository" and then select your new branch.

    - Fill in the title and description and hit "Create pull request".

4. Respond to review comments:

    - Once your pull request is submitted, a member of the WATTS core
      development team will review it. The reviewer may make suggestions and
      commments to improve the overall quality of the code and ensure it is
      consistent with the rest of the codebase.

    - If changes are requested, make new commits on your local branch and then
      push them once again to the branch on your fork, which will update the
      pull request.

    - GitHub also enables reviewers to make suggested changes to specific lines
      of code. In this case, you can agree to these changes directly from GitHub
      following the `directions here`_.

    - Once the reviewer is satisfied that their feedback has been addressed,
      they will approve and merge your branch.

5. 🎉 Celebrate! 🎉

.. _directions here: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/incorporating-feedback-in-your-pull-request

.. _checklist:

Contribution Checklist
++++++++++++++++++++++

All contributions to WATTS are reviewed and must meet certain level of quality
to be considered for merging. Before you submit a pull request, please run
through the following checklist to ensure a smooth review:

- If you are adding a new feature, it must be accompanied by tests. This ensures
  that future changes will not break your feature as the tests are run via
  continuous integration (CI) each time a pull request is submitted.

- Code must be sufficiently documented. Python classes and functions must
  include docstrings that describe the purpose and all arguments and return
  values.

- Code should conform to our :ref:`style guide <style_guide>`.

- All tests must pass. To run the test suite locally, you need to have pytest_
  installed. Once that is done, from the root directory of the repository simply
  run::

    pytest tests

.. _pytest: https://docs.pytest.org/

Review Process
++++++++++++++

Once your pull request is submitted, a member of the WATTS core development team
will review your pull request. They will check your contribution against the
above checklist to ensure that it is of sufficient quality.

.. _install_develop:

Installation for Developers
+++++++++++++++++++++++++++

As a developer, it is advisable to install WATTS from the local source tree in
"`editable <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_"
mode::

  pip install -e <path-to-watts-dir>

This will install the package via a link to the original location so that any
local changes are immediately reflected in your environment.
