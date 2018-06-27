```
odm-user ezekielh list-items > ezekielh.json
odm-list ezekielh.json list-filenames | grep ^/testdir > ezekielh.exclude
odm-list ezekielh.json download-items --dest /var/tmp/ezekielh --exclude ezekielh.exclude
```

Quick benchmarks:
* 0.68 seconds per file with negligibly tiny files
* 53.3 GiB/hour for one large file
