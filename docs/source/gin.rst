Walk-through: Dataset hosting on GIN
####################################

In this walkthrough, we will use DataLad Gooey to create a dataset, save it contents,
and publish it to `GIN <https://gin.g-node.org>`_ (G-Node Infrastructure).

Prerequisites
-------------

.. todo:: note about having ssh key set up

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

.. todo: screenshot

Save the contents
-----------------

Right-click the newly created dataset, and select *Dataset commands* → *Save the state in a dataset*.
Parameters required for the Save command should appear in the Command tab.
Fill in the *description of change* (this is the commit message associated with the save).
Leave all other fields default (note: *Do not put files in annex* is greyed out, not checked, i.e. it has no value).
Here, we are saving all files at once, but if we wanted we cauld limit the save operation to selected files,
or trigger it by clicking on a specific file.
Once ready, click OK.

.. todo: screensho
