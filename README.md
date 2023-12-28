# nacos-cli

cli client for nacos

```
python3 nacos-cli.py --username nacos --password nacos \
    --host "http://localhost:8848" --namespace "xxxxx-xxxxx-xxxxx-xxxx-xxxxxxx" \
    --command "list-instances" --watch --services myapp1,myapp2
```