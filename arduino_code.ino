#include <TM1637Display.h>

#define BUTTON_1_PIN 9      
#define BUTTON_2_PIN 8      
#define BUZZER_PIN 3        
#define CLK_PIN 10          
#define DIO_PIN 11          

TM1637Display display(CLK_PIN, DIO_PIN);

const int MAX_TIMERS = 10;
unsigned long timerDurations[MAX_TIMERS];
int timerCount = 0;
int currentTimerIndex = 0;
unsigned long timerStart = 0;
bool timerRunning = false;

void setup() {
  Serial.begin(9600);  // Initialize Serial communication
  pinMode(BUTTON_1_PIN, INPUT_PULLUP);
  pinMode(BUTTON_2_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);

  display.setBrightness(0x0f);
  display.showNumberDecEx(0, 0b11100000, true); 
}

void loop() {
  if (digitalRead(BUTTON_1_PIN) == LOW) {
    addTimer((10000));  
    delay(300);  
  }
  else if (digitalRead(BUTTON_2_PIN) == LOW) {
    addTimer((60000)*15);  
    delay(300);  
  }

  if (!timerRunning && currentTimerIndex < timerCount) {
    startTimer(timerDurations[currentTimerIndex]);
  }

  if (timerRunning) {
    unsigned long elapsedTime = millis() - timerStart;
    unsigned long remainingTime = (timerDurations[currentTimerIndex] - elapsedTime) / 1000;

    if (remainingTime > 0) {
      displayTime(remainingTime);  
    } else {
      playBuzzerSound();
      sendReadyNotification();  // Notify server when pizza is ready
      timerRunning = false;        
      currentTimerIndex++;        
      display.showNumberDecEx(0, 0b11100000, true); 
      delay(500);
    }
  }
}

void addTimer(unsigned long duration) {
  if (timerCount < MAX_TIMERS) {
    timerDurations[timerCount] = duration;
    timerCount++;
  }
}

void startTimer(unsigned long duration) {
  timerStart = millis();
  timerRunning = true;
}

void displayTime(unsigned long timeInSeconds) {
  int minutes = timeInSeconds / 60;
  int seconds = timeInSeconds % 60;
  int displayValue = (minutes * 100) + seconds;

  display.showNumberDecEx(displayValue, 0b11100000, true);
}



void playBuzzerSound() {
  for (int i = 0; i < 3; i++) {        // Repeat beep 3 times
    tone(BUZZER_PIN, 2000);    // Turn on the buzzer
    delay(200);                         // Buzzer on for 200 ms
    noTone(BUZZER_PIN);     // Turn off the buzzer
    delay(200);
  }
}

void sendReadyNotification() {
  Serial.println("{\"message\":\"pizza\"}");
  delay(1000);
}
