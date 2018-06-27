```
odm-user ezekielh list-items -v > ezekielh.json
odm-list ezekielh.json list-items | grep ^/testdir > ezekielh.exclude
odm-list ezekielh.json download-items --dest /var/tmp/ezekielh --exclude ezekielh.exclude
```
