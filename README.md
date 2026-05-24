# Este script busca dados de consumo no site do SAAE e atualiza o Home Assistant com estes dados

No Home Assistant, deve ser criado um sensor como segue:

```yaml
sensor:
  - name: "SAAE Consumo Mensal"
      unique_id: "saae_consumo_mensal"
      state: "{{ states('input_number.saae_consumo_mensal') | float(0) }}"
      unit_of_measurement: "m³"
      device_class: water
      state_class: measurement
      icon: mdi:water
```
Para rodar o script, criar um arquivo .env na mesma pasta do arquivo cpfl.py com os seguintes dados:
```
USER_NAME="seu usuário no SAAE"
PASSWORD="sua senha no SAAE"
HA_URL=http://IpdoHomeAssistant:8123
HA_WS_URL=ws://IpdoHomeAssistant:8123/api/websocket
HA_TOKEN="token criado no Home Assistant"
```