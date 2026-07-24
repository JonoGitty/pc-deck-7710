/* WiFi, and the two lookups that need it. See deck_net.c. */
#ifndef DECK_NET_H
#define DECK_NET_H

#include "meta.h"

int  deck_net_start(const char *ssid, const char *pass);
int  deck_net_is_up(void);

/* Fetch synced lyrics for whatever `m` currently holds and fill its rows.
 * Runs on its own task; returns immediately. Re-entrant calls for the same
 * track are ignored, which matters because a track change fires several
 * AVRCP notifications. */
void deck_net_want_lyrics(deck_meta_t *m, int cells);

#endif /* DECK_NET_H */
