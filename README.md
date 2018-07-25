# ODM

ODM is a set of tools for administratively downloading content from OneDrive
to a local directory tree without the involvement of the end user. It also
includes a tool for administratively uploading a local directory tree to Google
Drive.

ODM is currently in beta. It has undergone some testing, but the codebase is
still very new and in flux.

## Setting up your environment

This tool was written and tested using Python 2.7.14 on Linux. Portions of the
code were also tested under various versions of Python >= 3.4.

We recommend using a virtualenv to install ODM's Python dependencies.

* Run `init.sh` to set up the virtualenv
* When you want to use ODM, source env-setup.sh (`. env-setup.sh`) to set up the
  necessary environment variables.

## Credentials

The odm tools require credentials for an authorized Azure AD 2.0 client.
The gdm tool requires credentials for an authorized Google service account.

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

* Do the needful

## Downloading from OneDrive
```
odm-user ezekielh list-items > ezekielh.json
odm-list ezekielh.json list-filenames | grep ^testdir > ezekielh.exclude
odm-list ezekielh.json download-estimate --exclude ezekielh.exclude
odm-list ezekielh.json download-items --dest /var/tmp/ezekielh --exclude ezekielh.exclude
odm-list ezekielh.json verify-items --dest /var/tmp/ezekielh --exclude ezekielh.exclude -v
odm-user ezekielh list-items --incremental ezekielh.json > ezekielh-incr.json

odm-user ezekielh list-notebooks > ezekielh-onenote.json
odm-list ezekielh-onenote.json convert-notebooks --dest '/var/tmp/ezekielh/Exported from OneNote'
```

## Uploading to Google Drive
```
gdm /var/tmp/ezekielh ezekielh upload-files --dest "Magically Delicious"
gdm /var/tmp/ezekielh ezekielh verify-files --dest "Magically Delicious"
```

## Known Limitations

* OneDrive filenames can be up to 400 characters in length, while most Unix
  filesystems only allow 255 bytes. If ODM encounters a filename or path
  component that is more than 255 bytes, it keeps the filename as long as
  possible and adds leading directory components containing the rest of the
  original filename.

* OneNote files can be downloaded via the OneDrive API, but they do not have an
  associated hash and do not reliably report the actual download size via the
  API, so no verification is possible.

* OneDrive will sometimes return an incorrect file hash when listing files.
  Once the file has been downloaded, the API will then return the correct
  hash.

* Microsoft use a non-standard fingerprinting method for files in OneDrive for
  Business. ODM includes an incredibly slow pure Python implementation of this
  algorithm so that file verification works out of the box, but if you are
  dealing with any significant amount of data fingerprint calculation can be
  sped up quite a bit by installing
  [libqxh](https://github.com/flowerysong/quickxorhash).

## Notes on OneNote exports

* Here be drekavac.

* The OneNote API does not return any content for certain types of page
  elements, so mathematical expressions (and possibly some other node types)
  will be lost in conversion.

* The OneNote API is heavily throttled.
