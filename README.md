# ODM

ODM is a set of tools for administratively downloading content from OneDrive
to a local directory tree without the involvement of the end user. It also
includes a tool for administratively uploading a local directory tree to Google
Drive.

## Setting up your environment

This tool was mainly written and tested using Python 2.7 on Linux. Portions of
the code were also tested under various versions of Python >= 3.4.

For development, we recommend using a virtualenv to install ODM's Python
dependencies.

* Run `init.sh` to set up the virtualenv
* When you want to use ODM, source env-setup.sh (`. env-setup.sh`) to set up the
  necessary environment variables.

## Credentials

The odm command requires credentials for an authorized Azure AD 2.0 client.
The gdm command requires credentials for an authorized Google service account.

### Azure AD 2.0

* Register your client at https://apps.dev.microsoft.com/ (Azure AD 2.0 clients
  are also called "Converged applications").
    * Under `Application Secrets` select `Generate New Password`; use this as
      the `client_secret` in your ODM config.
    * Under `Platforms`, add a web platform with a redirect URL of
      `https://localhost` (with the authentication flow we're using this URL is
      not useful in any way, but it can't be omitted)
    * Under `Microsoft Graph Permissions` add the necessary `Application
      Permissions`:
        * User.Read.All
        * Files.Read.All
        * Notes.Read.All
* Grant permissions for your tenant by visiting
  https://login.microsoftonline.com/common/adminconsent?client_id=FOO&redirect_uri=https://localhost
  while logged in as an admin.
    * FOO should be replaced with the client ID that you registered
    * If this step is successful you should be redirected to https://localhost/?admin_consent=True&tenant=BAR, which will probably fail to load.

### Google Service Account

* Create a project at
  https://console.developers.google.com/cloud-resource-manager
* Inside the project, create a service account.
    * Name the account something meaningful.
    * The account does not require any roles.
    * Select `Furnish a new private key` and the JSON key type.
    * Enable `G Suite Domain Wide Delegation`
    * Creating the account will download a JSON file; use this as the
      `credentials` in your ODM config.
* Inside the project, enable the Google Drive API.
    * Open the navigation menu by clicking the three bars icon at the top left.
    * Click `APIs & Services`
    * Click `ENABLE APIS AND SERVICES`
    * Find `Google Drive API`
    * Click `ENABLE`
* As a super-admin, authorize the scopes at https://admin.google.com/
    * Click `Security`
    * Click `Advanced settings`
    * Click `Manage API client access`
    * Enter the client ID and authorize it for
      `https://www.googleapis.com/auth/drive`

## Downloading from OneDrive

Individual operations are designed to be idempotent and cleanly
resumable. Because fetching metadata for large drives is a very
expensive operation (both in volume of API calls and time) it's done
as a separate step, and the download operations use this cached
metadata file instead of the live API.

### Fetch metadata

```
odm user ezekielh show
odm user ezekielh list-drives
odm user ezekielh list-items > ezekielh.json
```

### Download items

Downloaded files are verified as they're saved, but you can also re-check the
state of previously downloaded files as a separate operation, or clean up
an existing destination folder by deleting extraneous files.

```
odm list ezekielh.json list-filenames
odm list ezekielh.json download-estimate
odm list ezekielh.json download --dest /var/tmp/ezekielh
odm list ezekielh.json verify --dest /var/tmp/ezekielh
odm list ezekielh.json clean-filetree --dest /var/tmp/ezekielh
```


### Convert OneNote notebooks

OneNote has a rudimentary API that allows some but not all note data to be
extracted and converted to HTML documents.

```
odm user ezekielh list-notebooks > ezekielh-onenote.json
odm list ezekielh-onenote.json convert-notebooks --dest '/var/tmp/ezekielh/Exported from OneNote'
```

## Uploading to Google Drive

```
gdm filetree /var/tmp/ezekielh upload ezekielh --dest "Magically Delicious"
gdm filetree /var/tmp/ezekielh verify ezekielh --dest "Magically Delicious"
```

## Known Limitations

* The modification time of individual files is preserved, but no attempt is made
  to preserve the mtime of folders.

* OneDrive filenames can be up to 400 characters in length, while most Unix
  filesystems only allow 255 bytes (which could be as few as 63 UTF-8
  characters.) If ODM encounters a filename or path component that is more than
  255 bytes it chunks the excess characters into leading directory components.

* OneNote files can be downloaded via the OneDrive API, but they do not have an
  associated hash and do not reliably report the actual download size via the
  API so no verification is possible.

* OneDrive will sometimes return an incorrect file hash when listing files.
  Once the file has been downloaded, the API will then return the correct
  hash.

* Files detected as malware by OneDrive's scanning cannot be downloaded via
  the API.

* Microsoft use a non-standard fingerprinting method for files in OneDrive for
  Business. ODM includes an incredibly slow pure Python implementation of this
  algorithm so that file verification works out of the box, but if you are
  dealing with any significant amount of data fingerprint calculation can be
  sped up quite a bit by installing
  [libqxh](https://github.com/flowerysong/quickxorhash).

## Migration Tooling

ODM is fairly well tested at this point, having been used at the University of
Michigan to do a one-time migration of ~6000 users with a total of 5 TiB of
data. An example migration script can be found in the contrib directory.

## Further Information On OneNote Exports

* Most of ODM's magic is like the wardrobe to Narnia. OneNote exports are more
  akin to the Lament Configuration.

* The OneNote API does not return any content for certain types of page
  elements, so mathematical expressions (and possibly some other node types)
  will be lost in conversion.

* The OneNote API is heavily throttled.
