This Python script exports all the OneNote notebooks linked to your Microsoft account to HTML files.

## Setup
In order to run the script, you must first do the following:
1. Clone the repo using `git clone https://github.com/Danmou/onenote_export.git`
2. Go to https://aad.portal.azure.com/ and log in with your Microsoft account.
3. Select "Azure Active Directory" and then "App registrations" under "Manage".
4. Select "New registration". Choose any name, set "Supported account types" to "Accounts in any 
   organizational directory and personal Microsoft accounts" and under "Redirect URI", select Web 
   and enter `http://localhost:5000/getToken`. Register.
5. Copy "Application (client) ID" and paste it as `client_id` in `config.yaml`.
6. Select "Certificates & secrets" under "Manage". Press "New client secret", choose a name and 
   confirm.
7. Copy the client secret and paste it as `secret` in `config.yaml`.
8. Select "API permissions" under "Manage". Press "Add a permission", scroll down and select OneNote, 
   choose "Delegated permissions" and check "Notes.Read" and "Notes.Read.All". Press "Add 
   permissions".
9. Make sure you have Python 3.7 (or newer) installed and install the dependencies using the command 
   `pip install -r requirements.txt`.

## Running
In a terminal, navigate to the directory where this script is located and run it using 
`python onenote_export.py`. This will start a local web server on port 5000. 
In your browser navigate to http://localhost:5000 and log in to your Microsoft account. 
The first time you do it, you will also have to accept that the app can read your OneNote notes. 
(This does not give any third parties access to your data, as long as you don't share the client id 
and secret you created on the Azure portal). After this, go back to the terminal to follow the progress.

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
The notebooks will each become a subdirectory of the `output` folder, with further subdirectories 
for the sections within each notebook and the pages within each section. Each page is a directory 
containing the HTML file `main.html` and two directories `images` and `attachments` (if necessary) 
for the images and attachments. Any sub-pages will be subdirectories within this one.

## Note
Microsoft limits how many requests you can do within a given time period. Therefore, if you have many 
notes you might eventually see messages like this in the terminal: "Too many requests, waiting 20s and 
trying again." This is not a problem, but it means the entire process can take a while. Also, the login 
session can expire after a while, which results in a TokenExpiredError. If this happens, simply reload 
`http://localhost:5000` and the script will continue (skipping the files it already downloaded).
