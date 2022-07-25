# tgosint

This project aims to parse telegram channels specified and find info you want in channel history.

## Main steps
 1. make channels list
 2. parse it daily
 3. watch for the info you want
 4. creation of locked channels, where you want to send notifications about findings

## Restrictions
 1. You need a valid telegram account with tied phone number
 2. You cannot parse locked channels until you are not in them


## What you need to get started
 - make telegram channels list
 - make patterns list
 - clone repositories
 - make list of github repos (currently you can parse only specific [repo](https://github.com/alexnest-ua/targets) but it is not hard to add some abstractions for common cases)

## Some info

When you run the script firstly it would save the channels data in specific *data directory* which was specified in the config file. To parse only actual massages for each channel the **message_offset** is created - it is the id of the latest seen message. Output formats: csv or json. You can write simple function for history search if you want. The script returns findings via RocketChat or telegram. For RocketChat you need channel hook, where bot would send findings and server domain name, for telegram: api_id and api_hash you can read about it [here](https://core.telegram.org/api/obtaining_api_id), username, bot token and channel, where bot would send findings. The first run requires authentication of telegram user. After that the **username.session** would be created.

## And for the laziest of us

1. `git clone https://github.com/St-elin/tgosint.git`
2. `python3 -m venv <venv>`
3. `source <venv>/bin/activate`
4. `cd tgosint`
5. `pip install -r requirements.txt`
6. `python tgosint.py`

# If you want to add any functionality feel free to do fork or do it by your own.