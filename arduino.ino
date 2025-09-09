#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 10
#define RST_PIN 9
#define BUZZER_PIN 8  // Buzzer na porta 8

MFRC522 mfrc522(SS_PIN, RST_PIN);

// Lista de cartões autorizados
String authorizedTags[] = {"3A163602", "AD88C801"}; // IDs do seu Python

void setup() {
  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  pinMode(BUZZER_PIN, OUTPUT);
  Serial.println("RFID leitor iniciado");
}

// Função para tocar sequência de bips
void beep(int *frequencies, int *durations, int count, int pause=50) {
  for (int i = 0; i < count; i++) {
    tone(BUZZER_PIN, frequencies[i], durations[i]);
    delay(durations[i] + pause);
  }
}

void loop() {
  // Verifica se há um novo cartão
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial()) return;

  // Lê o UID do cartão e formata como string de 8 caracteres
  String rfidTag = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) rfidTag += "0"; // adiciona zero à esquerda
    rfidTag += String(mfrc522.uid.uidByte[i], HEX);
  }
  rfidTag.toUpperCase(); // corrige: apenas chama o método, não atribui

  Serial.println(rfidTag);

  // Checa se o cartão está autorizado
  bool authorized = false;
  for (int i = 0; i < sizeof(authorizedTags)/sizeof(authorizedTags[0]); i++) {
    if (rfidTag == authorizedTags[i]) {
      authorized = true;
      break;
    }
  }

  // Toca o bip de acordo com autorização
  if (authorized) {
    // AUTORIZADO: sequência alegre de 3 bips curtos ascendentes
    int freqs[] = {1200, 1500, 1800};
    int times[] = {150, 150, 150};
    beep(freqs, times, 3, 100);
  } else {
    // NEGADO: sequência dramática de 3 bips graves descendentes
    tone(BUZZER_PIN, 800, 150); // Primeiro bip curto
    delay(200);
    tone(BUZZER_PIN, 800, 150); // Segundo bip curto
    delay(200);
  }

  // Pequeno delay para evitar leituras repetidas muito rápidas
  delay(500);
}
