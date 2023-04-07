This Python script exports all the OneNote notebooks linked to your Microsoft account to HTML files.

## Setup

In order to run the script, you must first do the following:
1. Clone the repo using `git clone https://github.com/Danmou/onenote_export.git`
2. Make sure you have Python 3.7 (or newer) installed and install the dependencies using the command 
   `pip install -r requirements.txt`.

If you wish to use your own client ID, go to https://aad.portal.azure.com/ and
log in with your Microsoft account. Select "Azure Active Directory" and then
"App registrations" under "Manage". Select "New registration", configure a new
application, and under "Authentication" scroll to "Advanced settings" and
enable "Allow public client flows". Copy the client ID from the "Overview"
section and set it as the `client_id` value in your `onenote_export.cfg` file
(by default, in `$HOME/.config/onenote_export.cfg`).

## Running

In a terminal, navigate to the directory where this script is located and run
it using `python onenote_export.py`. The first time you run it, this will
prompt you to approve OAuth access to your Microsoft account to open and read
your OneNote notes. 

To change the destination directory use the `--outdir` option:
```bash
python onenote_export.py --outdir /path/to/outdir
```

To download only a subset of your notes, use the `--select` option:
```bash
# Download one notebook
python onenote_export.py --select 'mynotebook'
# All matrix-related notes in the 'Linear Algebra' section of the 'Math' notebook.
python onenote_export.py --select 'math/linear algebra/*matrix*'
```
Select is case insensitive and supports wildcards.

## Output
The notebooks will each become a subdirectory of the `output` folder, with
further subdirectories for the sections within each notebook and the pages
within each section. Each page is a directory containing the HTML file
`main.html` and two directories `images` and `attachments` (if necessary) for
the images and attachments. Any sub-pages will be subdirectories within this
one.

## Note
Microsoft limits how many requests you can do within a given time period.
Therefore, if you have many notes you might eventually see messages like this
in the terminal: "Too many requests, waiting 20s and trying again." This is not
a problem, but it means the entire process can take a while. 
