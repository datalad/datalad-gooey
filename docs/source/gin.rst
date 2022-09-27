Walk-through: Dataset hosting on GIN
####################################

In this walkthrough, we will use DataLad Gooey to create a dataset, save it contents,
and publish it to `GIN <https://gin.g-node.org>`_ (G-Node Infrastructure).

Prerequisites
-------------

In order to use GIN for hosting and sharing your datasets, you need to:

  - Register a GIN account
  - Add a personal access token (for creation of repositories with DataLad)
  - Add an SSH key (for uploading annexed contents)

Follow the instructions on GIN to do so.
If you want to stay in the world of graphical interfaces, we recommend
`PuTTYgen <https://www.puttygen.com/>`_ for SSH keys generation.

Create a dataset
----------------

Let's assume that we are starting with an existing folder which already has some content, but is not yet a DataLad dataset.
Let's open the DataLad gooey and set a base directory to our folder, or its parent directory.

Our first operation is to to create a DataLad dataset.
For this, right-click your folder and select *Directory commands* → *Create a dataset*.
This will populate the Command tab on the right with options for the selected command. 
The first value (*Create at*) is already populated, since we used right-click to issue the command.
We leave *Dataset with file annex* checked (default), and *Register in superdataset* not set (default).
In this example we want to configure our dataset to annex binary, but not text files.
To do so, select *text2git* from the list of *Configuration procedure(s)* and click *Add*.
Finally, check the *OK if target directory not empty* to enforce dataset creation out of a non-empty folder.
With the options selected, click *OK*.

.. image:: /_static/screenshots-gin/created.png

Save the contents
-----------------

Right-click the newly created dataset, and select *Dataset commands* → *Save the state in a dataset*.
Parameters required for the Save command should appear in the Command tab.
Fill in the *description of change* (this is the commit message associated with the save).
Leave all other fields default (note: *Do not put files in annex* is greyed out, not checked, i.e. it has no value).
Here, we are saving all files at once, but if we wanted we cauld limit the save operation to selected files,
or trigger it by clicking on a specific file.
Once ready, click OK.

.. image:: /_static/screenshots-gin/saved.png

Create a GIN sibling
--------------------

Creating a GIN sibling will create a new repository on GIN, and configure your dataset with its address.
To perform this action, right-click your dataset, and select *Dataset commands* → *Create a GIN sibling*.
Fill in the *New repository name on Gin* (and, optionally, check the *Make GIN repository private*).
You can leave all other options default.

In the *Name of the credential to be used* field, you can pick previously used credentials.
If no value is given, and no previous credentials exist, the credentials will be save with website name (`gin.g-node.org`) by default.

Click OK.

At this point, you will be asked for a token.
Paste the access token generated from GIN website, and click OK.

.. image:: /_static/screenshots-gin/created-sibling.png

Push to the GIN sibling
-----------------------

Right-click *Dataset commands* → *Push data/updates to a sibling*.
The only thing you need to select is the value of *To dataset sibling* - this will be the sibling name from the step above.
Click OK.

.. image:: /_static/screenshots-gin/pushed.png

Retrieve the data from GIN
--------------------------

Finally we can confirm that our dataset can be obtained from GIN (possibly by other users who have access).

.. todo: describe cloning

