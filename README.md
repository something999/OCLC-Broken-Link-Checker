# OCLC Broken Link Checker
The **OCLC Broken Link Checker** is a Python-based application designed to detect inaccessible online resources within [OCLC (Online Computer Library Center)](https://www.oclc.org) collections. The application performs this task by:
* Retrieving collections from the OCLC databases.
* Fetching the [KBART](https://www.niso.org/standards-committees/kbart/kbart-frequently-asked-questions) for each collection.
* Extracting resource links from each KBART file.
* Sending HTTP HEAD requests to verify link access.
* Counting the number of requests that resolve to a non-200 status code.
* Flagging the collections that contain a proportion of links that exceed a configurable threshold.

# Installation & Configuration
## Part 1: Obtaining the WSKey
To collect the resources and KBARTs, the OCLC Broken Link Checker needs access to the [OCLC WorldCat Knowledge Base API](https://developer.api.oclc.org/kb). This API allows users to search for collections enabled by their institution.

To obtain the key:
1. Request a **WSKey** from the **[OCLC Developer Network](https://help.oclc.org/Librarian_Toolbox/OCLC_APIs/Get_started/Request_an_API_WSKey)**.
    - Submit a request for a **Production WSKey** designed for a **Machine-to-Machine (M2M) App** registered with the **WorldCat Knowledge Base API** service.
    - **Ensure that you have selected the correct institution before submitting the request**. The WSKey will only grant you access to collections registered under that institution.
        - **Example**: If you have accounts with Library A and Library B and request a WSKey under Library A, the key will only allow you to access collections from Library A.
2. Wait for the request to be approved.

If successful, you should be able to see your key in the **[Developer Network WSKey user interface](https://platform.worldcat.org/wskey)** under the **View WSKeys** tab.
* This key will be listed as ACTIVE and have the WorldCat Knowledge Base API listed under Services.

## Part 2: Downloading the Program
There are two ways to install this application:
1. **Download the executable file** (`oclc-broken-link-checker.exe`).
2. **Download the source package** (`.zip` or `tar.gz`).

**These files are located under the Releases tab on GitHub.**

Note that if you choose to download the executable file and run it, Windows may display a warning about running files from unknown publishers. This is expected behavior. If you trust the source, click **More info -> Run anyway** to continue (if not, use the source code package).

Currently, **official support is only provided for Windows 64-bit operating systems**.<br>
Windows 32-bit, Mac and Linux users may attempt to run the program using emulators (e.g, [Wine](https://www.winehq.org/)) or virtual machines (e.g, [Virtual Box](https://www.virtualbox.org)), but full functionality is not guaranteed.

### Choosing an Installation Approach
**Executable installation** is recommended if:
* You want to run the program from your file explorer.
* You are running a 64-bit version of Windows.
    * If you are not sure whether you are running a 64-bit version of Windows:
        1. Open the search box.
        2. Locate **System** or **System Information**.
        3. Look for the phrase **64-bit operating system, x64 based processor** or **x64-based PC** under System Type. If you see either of these phrases, your computer is running a 64-bit version of Windows (if not, you must use the source code package).

**Source package installation** is recommended if:
* You want to run the program directly in a Python IDE.
* You want to be assured of the executable contents.
* You plan to modify the code (e.g, change the behavior of `APIClient` or `HTTPClient`, create your own Mac distribution, etc.).
* You feel comfortable installing Python on your system.
* You feel comfortable installing external Python libraries in your global Python installation or within a virtual environment.

If you choose to download the source package, you will need to install Python3.11+ and the libraries listed under `requirements.txt`.

## Part 3: Configuring the Program.
Once you have obtained your WSKey and installed the program, you will need to modify the application settings.
1. **Run the OCLC Broken Link Checker application**.
2. Navigate to the **Settings** tab.
3. Locate the setting titled **WSKey (Required)** under Basic Settings.
4. **Copy and paste the ClientID portion of your WSKey into the associated input field**.
    * You do not need to use the Secret portion of your WSKey.
5. Click the **Save Config** button.
    * If successful, a message box appear confirming that the save operation was successful.

You may also want to look into the other application settings, such as:
* **Link Failure Threshold**: A number between 0.0 and 1.0 representing the maximum
    allowable percentage of broken links within a collection.<br>
    A value of 0.0 corresponds to 0%; a value of 1.0 corresponds to 100%.
    If at least this percentage of links are non-accessible, the entire collection is flagged as broken.<br>
    By default, this value is 0.0.
* **User-Agent**: A [string that provides technical information to web servers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/User-Agent). This can technically be any value.<br> By default, this value is empty.
    * Some websites may block your request if you fail to provide a User-Agent string.
* **Ignored Domains**: A list of domains that the application should skip during the link‑checking process.<br>
If a resource link belongs to one of these domains, the link will automatically be flagged as inaccessible (with a placeholder status code of `-1`).<br>By default, this list is empty.
    * You may want to use this list to exclude links from domains that explicitly forbid or actively block web scraping attempts or interpret frequent HTTP HEAD requests as web scraping-like behavior (e.g., [HathiTrust](https://www.hathitrust.org/the-collection/terms-conditions/acceptable-use-policy/)).

# Usage
## Basic Usage
The application runs in two modes:
* The **Quick Scan** mode, which uses the parent domain of each resource link to determine if a link is inaccessible.<br>
This mode assumes that if a domain is inaccessible, all of the links under that domain are also inaccessible.
    * **Example**: When checking Resource A (`https://example.com/A`) and Resource B (`https://example.com/B`), the application will test whether the parent domain `example.com` is accessible. The result of that check will then be applied to both Resource A and Resource B.
    * **Limitation**: A single failed domain test may cause all links under the domain to be flagged as inaccessible, leading to false positives.
* The **Full Scan** mode, which checks each resource link to determine if a link is inaccessible.<br>
This mode assumes that every link should be checked individually.
    * **Example**: When checking Resource A (`https://example.com`) and Resource B (`https://example.com/B`), the application will test both links. The results of these checks will be separately applied to Resource A and Resource B.
    * **Limitation**: Sending multiple HTTP requests to the same domain in rapid succession may trigger throttling or blocking attempts from the web server, leading to false positives.

**To start a scan, click on the corresponding button in the Home tab.**

### Choosing a Scan Mode
**Quick Scan** mode is recommended if:
- You have a large number of online resources to check.  
- The resources belong to repositories with a reputation for stability. 
- You favor speed over accuracy.

**Full Scan** mode is recommended if:
- You have a smaller number of online resources to check.  
- The resources belong to repositories with less predictable availability.
- You prefer accuracy over speed.

**No further action is needed. Results will be generated and appear within the text box in the Home Tab.**

## Advanced Usage
If you want a more detailed report explaining which links the application found or which links were flagged as broken, you can attempt the following:
1. Locate the **caches** folder in your application directory (automatically created upon application startup).
2. Open the file named **results_cache.csv**.

Each row should contain the following information:
* The resource's collection's OCLC identifier.
* The resource's OCLC identifier.
* The resource's title.
* The resource's URL.
* The status code recorded for that URL.

**Note that this file is temporary. Cache files are automatically cleared each time the application restarts.**

# Licenses
The OCLC Broken Link Checker project is distributed under the [MIT License](https://opensource.org/license/mit).

The project also makes use of third-party libraries that are distributed under other licenses.
Please refer to the `/licenses` folder for the full license texts and the `/notices` folder for any notices provided by those libraries.
* **aiodns**: MIT License (see `/licenses/aiodns.LICENSE`)
* **aiofiles**: Apache 2.0 License (see `/licenses/aiofiles.LICENSE` and `/notices/aiofiles.NOTICE`)
* **aiohappyeyeballs**: PSF-2.0 License (see `/licenses/aiohappyeyeballs.LICENSE`)
* **aiohttp**: Apache 2.0 License (see `/licenses/aiohttp.LICENSE` and `/licenses/aiohttp.full.LICENSE`)
* **aiosignal**: Apache 2.0 License (see `/licenses/aiosignal.LICENSE`)
* **altgraph**: MIT License (see `/licenses/altgraph.LICENSE`)
* **attrs**: MIT License (see `/licenses/attrs.LICENSE`)
* **backoff**: MIT License (see `/licenses/backoff.LICENSE`)
* **certifi**: Mozilla Public License 2.0 (see `/licenses/certifi.LICENSE` and `/licenses/certifi.full.LICENSE`)
* **cffi**: MIT No Attribution License (see `/licenses/cffi.LICENSE`)
* **charset-normalizer**: MIT License (see `/licenses/charset-normalizer.LICENSE`)
* **filelock**: MIT License (see `/licenses/filelock.LICENSE`)
* **frozenlist**: Apache 2.0 License (see `/licenses/frozenlist.LICENSE`)
* **idna**: BSD 3-Clause License (see `/licenses/idna.LICENSE.md`)
* **multidict**: Apache 2.0 License (see `/licenses/multidict.LICENSE`)
* **pefile**: MIT License (see `/licenses/pefile.LICENSE`)
* **propcache**: Apache 2.0 License (see `/licenses/propcache.LICENSE` and `/notices/propcache.NOTICE`)
* **pycares**: MIT License (see `/licenses/pycares.LICENSE`)
* **pycparser**: BSD 3-Clause License (see `/licenses/pycparser.LICENSE`)
* **pyinstaller**: GPL 2.0 License & Apache 2.0 License (see `/licenses/pyinstaller.COPYING.txt`)
* **pyinstaller-hooks-contrib**: GPL 2.0 License & Apache 2.0 License (see `/licenses/pyinstaller-hooks-contrib`)
* **pywin32-ctypes**: BSD 3-Clause License (see `/licenses/pywin32-ctypes.LICENSE`)
* **requests**: Apache 2.0 License (see `/licenses/requests.LICENSE` and `/notices/requests.NOTICE`)
* **requests-file**: Apache 2.0 License (see `/licenses/requests-file.LICENSE`)
* **tldextract**: BSD 3-Clause License (see `/licenses/tldextract.LICENSE`)
* **typing_extensions**: PSF-2.0 License (see `/licenses/typing_extensions.LICENSE`)
* **urllib3**: MIT License (see `/licenses/urlib3.LICENSE.txt`)
* **validators**: MIT License (see `/licenses/validators.LICENSE.txt`)
* **yarl**: Apache 2.0 License (see `/licenses/yarl.LICENSE` and `/notices/yarl.NOTICE`)