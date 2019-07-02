# ODM

ODM is a set of tools for administratively downloading content from
OneDrive to a local directory tree without the involvement of the end
user. It also includes tools for administratively uploading local
files to OneDrive or Google Drive.

## Setting up your environment

This tool was mainly written and tested using Python 2.7 on Linux. Portions of
the code were also tested under various versions of Python >= 3.4.

For development, we recommend using a virtualenv to install ODM's Python
dependencies.

* Run `init.sh` to set up the virtualenv
* When you want to use ODM, source env-setup.sh (`. env-setup.sh`) to set up the
  necessary environment variables.

## Credentials

The odm command requires credentials for an authorized Azure AD 2.0
client. Uploading OneNote files requires additional Sharepoint API
permissions and a client certificate.

The gdm command requires credentials for an authorized Google service
account.

### Azure AD 2.0

* Register your client at https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
    * Click `New registration`
    * Give your client a name and click `Register`
    * Use the displayed `Application (client) ID` as the `client_id` in your
      ODM config.
    * Under `Certificates & secrets` select `New client secret`; use this as
      the `client_secret` in your ODM config.
    * Create a certificate
        * `openssl req -x509 -days 3650 -nodes -newkey rsa:2048 -keyout key.pem -out cert.pem -subj '/CN=odm'`
        * Use the contents of key.pem as the `client_cert_key` in your ODM config.
        * Upload the certificate, then use the displayed thumbprint as the `client_cert` in your ODM config.
    * Under `API Permissions` add the necessary application
      permissions for Microsoft Graph:
        * User.Read.All
        * Files.ReadWrite.All
        * Notes.ReadWrite.All
        * Sites.FullControl.All
    * and the necessary application permissions for Sharepoint:
        * Sites.FullControl.All
    * Grant admin consent for your tenant by clicking on the button.
    * FIXME: should we document getting admin consent for other domains?


### Google Service Account

* Create a project at
  https://console.developers.google.com/cloud-resource-manager
* Inside the project, create a service account.
    * Name the account something meaningful.
    * The account does not require any roles.
    * Select `CREATE KEY` and the JSON key type; use the downloaded file as the `credentials` in your ODM config
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
odm user ezekielh list-items --incremental ezekielh.json > ezekielh-$(date +%f).json
```

### Download items

Downloaded files are verified as they're saved, but you can also re-check the
state of previously downloaded files as a separate operation, or clean up
an existing destination folder by deleting extraneous files.

```
odm list ezekielh.json list-filenames
odm list ezekielh.json download-estimate
odm list ezekielh.json download --filetree /var/tmp/ezekielh
odm list ezekielh.json verify --filetree /var/tmp/ezekielh
odm list ezekielh.json clean-filetree --filetree /var/tmp/ezekielh
```

### Upload items

```
odm list ezekielh.json upload --filetree /var/tmp/ezekielh --upload-user flowerysong
odm list ezekielh.json upload --filetree /var/tmp/ezekielh --upload-user flowerysong --upload-path 'other users/ezekielh'
odm filetree /var/tmp/ezekielh upload --upload-user flowerysong --upload-path 'other users/ezekielh'
```

### Convert OneNote notebooks

OneNote has a rudimentary API that allows some but not all note data to be
extracted and converted to HTML documents.

```
odm user ezekielh list-notebooks > ezekielh-onenote.json
odm list ezekielh-onenote.json convert-notebooks --filetree '/var/tmp/ezekielh/Exported from OneNote'
```

## Uploading to Google Drive

```
gdm filetree /var/tmp/ezekielh upload --upload-user ezekielh --upload-path "Magically Delicious"
gdm filetree /var/tmp/ezekielh verify --upload-user ezekielh --upload-path "Magically Delicious"
```

## Known Limitations

* The modification time of individual files is preserved wherever possible, but
  no attempt is made to preserve the mtime of folders.

* It is possible for additional owners to be added to files in a user's OneDrive
  by poking deep into the bowels of the SharePoint web interface; this is not
  possible via the OneDrive API and no attempt is made to preserve these
  permissions.

* Shared links are not recreated during upload; this functionality *is* exposed
  via the API, but it's not clear that it would be useful behaviour.

* Files uploaded to OneDrive will show up as last modified by `SharePoint App`;
  it is impossible to preserve the original modification information or have it
  display a less generic name.

* OneDrive is normally provisioned on a JIT basis when the user accesses the
  service, rather than at the time of account creation / license assignment.
  ODM cannot upload to OneDrive unless the drive is provisioned. SharePoint
  Online [provides an API endpoint](https://docs.microsoft.com/en-us/previous-versions/office/developer/sharepoint-rest-reference/dn790354%28v=office.15%29#createpersonalsiteenqueuebulk-method)
  for requesting the asynchronous bulk creation of drives. ODM does not
  currently have the ability to call this API, but PowerShell tools exist to
  request bulk creation using SharePoint Admin credentials. Once requests were
  put into the black box we observed widely varying provisioning rates ranging
  between ~80/hour and ~240/hour.

* OneDrive filenames can be up to 400 characters in length, while most Unix
  filesystems only allow 255 bytes (which could be as few as 63 UTF-8
  characters.) If ODM encounters a filename or path component that is more than
  255 bytes it chunks the excess characters into leading directory components.
  Metadata-based uploads (`odm list upload`) will upload as the original name,
  but filetree-based uploads (`odm filetree` or `gdm filetree`) will not.

* OneNote files can be downloaded via the OneDrive API, but they do not have an
  associated hash and do not reliably report the actual download size via the
  API so no verification is possible.

* Due to a limitation in the OneNote API any notebook upload will create a
  `Notebooks` directory in the root of the drive, even if the final destination
  is not underneath that location.

* OneDrive will sometimes return an incorrect file hash when listing files.
  Once the file has been downloaded, the API will then (usually) return the
  correct hash.

* OneNote is fragile and breaks easily. It sometimes fails to render sections
  uploaded via the API even though they are bit-exact copies of what was
  originally downloaded. We do not know why.

* Files detected as malware by OneDrive's scanning cannot be downloaded via
  the API.

* Microsoft use a non-standard fingerprinting method for files in OneDrive for
  Business. ODM includes an incredibly slow pure Python implementation of this
  algorithm so that file verification works out of the box, but if you are
  dealing with any significant amount of data fingerprint calculation can be
  sped up quite a bit by installing
  [libqxh](https://github.com/flowerysong/quickxorhash).

## Further Information On OneNote Exports

* Most of ODM's magic is like the wardrobe to Narnia. OneNote exports are more
  akin to the Lament Configuration.

* The OneNote API does not return any content for certain types of page
  elements, so mathematical expressions (and possibly some other node types)
  will be lost in conversion.

* The OneNote API is heavily throttled.
