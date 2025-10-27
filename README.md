# eventdataparser
CSR2 Event Data Parser

Usage : python .\main.py

<img width="1355" height="1110" alt="image" src="https://github.com/user-attachments/assets/edffac31-21b1-40b5-9b6d-196cfe71c409" />


- Extract any unity assets within the home folder structure, creating the correct output folders for the resources to sit in
- Process TranslationDataAsset.json that has been extracted from a Localisation_EN.ASTC file, if not you will need to manually provide one in a MonoBehaviour sub folder. This stores all the human readable text strings used.
- Process EventSchedule.meta, this will need to be provided manually and put it into the MetaData folder, a sample has been included but this will need to be manually updated for future releases. 
- Process ShopTimeGatedEvents.meta, this will need to be provided manually and put it into the MetaData folder, a sample has been included but this will need to be manually updated for future releases
- Process CollectionSlots.meta, this will need to be provided manually and put it into the MetaData folder, a sample has been included but this will need to be manually updated for future releases

- Process extracted TextAsset files for events
<img width="655" height="657" alt="image" src="https://github.com/user-attachments/assets/14160877-c54b-4cbe-8934-7691367a9815" />


- Process extracted TextAsset files for milestone seasons
<img width="581" height="275" alt="image" src="https://github.com/user-attachments/assets/6fef24d4-e01e-4e8e-8b8f-83c5a6e5b662" />


- Process extracted TextAsset files for Showdown Events, fetch the latest WR times from Nitro4CSRs github.
<img width="1107" height="812" alt="image" src="https://github.com/user-attachments/assets/66cbf49d-9b2b-473c-a498-429f217dc269" />


- Process extracted TextAsset files for Tournaments.
<img width="791" height="365" alt="image" src="https://github.com/user-attachments/assets/d3bcf0f3-b8c4-45e1-be88-f2e8c1c7e546" />






