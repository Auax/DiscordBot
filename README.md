# Auax Music Bot
This is an open source bot created with the Discord Python library.

## Prefix
The default prefix is set to: `!` or `/`.

## Configuration
It's important to change the `authentication.json` file and set your own tokens.

---
## Commands
| Command| Details                                                                                                          |
| -------| -------                                                                                                          |
| **join**   | joins a voice a channel                                                                                          |
| **summon** | summons the bot to a voice channel. If no channel was specified, it joins your channel.                          |
| **play**   | plays the song based on a YouTube URL or a title query. If there is a song playing already, this will be queued. |
| **leave**  | clears the queue and leaves the voice channel.                                                                   |
| **volume** | sets the volume of the player.                                                                                   |
| **now**    | displays the currently playing song.                                                                             |
| **pause**  | pauses the current song.                                                                                         |
| **resume** | resumes the paused song.                                                                                         |
| **stop**   | stops playing the song and clears the queue.                                                                     |
| **skip**   | vote to skip a song. Default number of users required to skip a song is 1/1. This can be changed.                |
| **queue**  | shows the player's queue.                                                                                        |
| **shuffle**| shuffles the queue.                                                                                              |
| **remove** | removes a song from the queue at a given index.                                                                  |
| **loop**   | loops the currently playing song. Repeat the same command to unloop the song.                                    |
