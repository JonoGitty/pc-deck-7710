/* C side for the text helpers — prints the same lines as render_text.js. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../core/text.h"

#define BUF 512
#define MAXROWS 24
#define ROWCAP 64

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "tools/verify/text.tsv";
  FILE *f = fopen(path, "r");
  if (!f) { perror(path); return 1; }

  char line[1024];
  while (fgets(line, sizeof line, f)) {
    if (line[0] == '/' || line[0] == '\n') continue;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;

    char *fld[4], *p = line;
    int ok = 1;
    for (int i = 0; i < 4; i++) {
      char *t = strchr(p, '\t');
      if (!t) { ok = 0; break; }
      *t = 0; fld[i] = p; p = t + 1;
    }
    if (!ok) continue;

    const char *name = fld[0], *kind = fld[1];
    const int a = atoi(fld[2]), b = atoi(fld[3]);
    const char *text = p;

    char folded[BUF];
    deck_fold(text, folded, sizeof folded);

    if (strcmp(kind, "fold") == 0) {
      printf("%-18s |%s|\n", name, folded);

    } else if (strcmp(kind, "wrap") == 0) {
      static char rows[MAXROWS * ROWCAP];
      int n = deck_wrap(folded, a, rows, ROWCAP, MAXROWS);
      printf("%-18s |", name);
      for (int i = 0; i < n; i++)
        printf("%s%s", i ? "/" : "", rows + (size_t)i * ROWCAP);
      printf("|\n");

    } else if (strcmp(kind, "scroll") == 0) {
      deck_scroll_t sc = { 0, 0, 0.0 };
      char win[BUF];
      printf("%-18s |", name);
      for (int i = 0; i < b; i++) {
        deck_scroll(&sc, 100.0, folded, a, win, sizeof win);
        printf("%s%s", i ? "/" : "", win);
      }
      printf("|\n");
    }
  }
  fclose(f);
  return 0;
}
