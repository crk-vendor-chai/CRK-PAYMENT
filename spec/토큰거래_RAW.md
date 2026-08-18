![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성부서

SW

작성자

강상호

MODEL

1. 기본 패킷 구성도

STX(1) Length(2)

Service Code(2)

Message Type(2)

DATA(n)

ETX(1)

LRC(1)

STX = 0x02, 전문 시작 구분자

ETX = 0x03, 전문 종료 구분자

FS = 0x1C, 항목 구별 구분자

Length\_H,L = 전문 전체길이 ( LRC 포함, Ex. 123길이 인 경우 0x01, 0x23 )

Service Code\_H,L = 기능별 코드

Message Type\_H,L = 요청, 응답 구분 타입

Data = Service Code에 따라 데이터 양식 따름

※ LRC : Length\_H ~ ETX 까지 계산 ( XOR 연산 )

2. 기본 안내

a

an

ans

b

Alphabetic. ‘a~z’

Alphabetic ‘a~z, A~Z, 0-9’

Alphabetic ASCII, 0x20~0x7f(ISO-8859)

Unsigned binary numbers

Numeric, 0~9

A

h

Alphabetic ‘A~Z’

Hexadecimal ‘0~9’, ‘a~f’

Hexadecimal ‘0~9’, ‘A~F’

Ksc 5601 완성형 한글코드

Binary-coded decimal

H

ksc

bcd

n

거래구분

성인인증

기능

인증

인증

생성

전문

AC

세부설명

성인인증을 위한 기능

거래시작요청

토큰생성

PS

거래시작을 서버로 알리는 기능

TQ

신용거래에 대한 토큰 생성 요청

- 실제 거래 승인은 이루어지지 않음, 토큰만 응답 받음

VANKEY와 TOKEN(HASH)값을 가지고 승인요청

D8거래에 대한 일반 취소

토큰신용 승인

토큰신용 취소

삼성페이

승인

취소

인증

D8

D9

PA

삼성페이 거래시작을 서버로 알리는 기능

거래시작요청

삼성페이 신용승인

삼성페이 신용취소

RF 사원증 확인

단말기 상태 확인

승인

취소

D1

D7

PR

PC

삼성페이 신용승인 요청, VANKEY 응답

VANKEY를 가지고 삼성페이 승인 취소

RF UID 전송 기능

단말기 연결 상태 확인

구분

기능

거래구분

세부설명

Service Code

Service Code에 따라 기능을 구분함 ( AC, TQ, D8, D9 )

1

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

Message Type

요청/응답

요청일 경우 10, 응답일 경우 20

3. 거래 흐름도

토큰 승인/취소

CAT

Server

거래시작 명령(Service Code “PS”)

거래시작 명령 응답(Service Code “PS”), 응답 주지 않아도 됨

토큰생성 명령(Service Code “TQ”)

토큰생성 후 응답(Service Code “TQ”, Message Type 20)

토큰신용승인/취소 요청(Service Code “D8”, “D9”)

토큰신용승인/취소 응답(Service Code “D8”, “D9”)

거래 종료

2

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

삼성페이 승인/취소

거래시작 명령(Service Code “PA”)

MODEL

CAT

Server

거래시작 명령 응답(Service Code “PA”), 응답 주지 않아도 됨

삼성페이 승인 요청(Service Code “D1”)

삼성페이 승인 후 응답(Service Code “D1”, Message Type 20)

삼성페이 승인 요청(Service Code “D1”)

삼성페이 승인 요청(Service Code “D1”)

삼성페이 승인 취소 요청(Service Code “D7”)

삼성페이 승인 취소 응답(Service Code “D7”)

거래 종료

3

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

4. 거래 구분 상세 내용

[POS-> CAT]

성인인증 확인 요청전문

순번

내용

SIZE

1

속성

a

비고

1

2

2

3

4

5

6

STX

0x02

전문 길이

Service Code

Message Type

FS

2

bcd

an

n

STX부터 CRC 까지

2

“AC”

2

10

1

a

0x1C

0x03

LRC Data

ETX

1

a

LRC

1

a

[CAT -> POS]

성인인증 확인 응답전문

순번

1

내용

SIZE

속성

비고

STX

1

2

a

0x02

2

전문 길이

bcd

an

n

STX부터 CRC 까지

3

Service Code

2

“AC”

4

Message Type

2

20

5

FS

1

a

0x1C

6

QR코드

FS

가변

1

ksc

a

성인인증 데이터

0x1C

7

8

알림

FS

가변

1

ksc

a

화면표시 알림 메시지

0x1C

9

10

11

ETX

LRC

1

a

0x03

1

a

LRC Data

4

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

[CAT -> POS]

거래시작 요청전문

순번

내용

SIZE

1

속성

a

비고

1

2

2

3

4

5

6

STX

0x02

전문 길이

Service Code

Message Type

FS

2

bcd

an

n

STX부터 CRC 까지

2

“PS”

2

10

1

a

0x1C

0x03

LRC Data

ETX

1

a

LRC

1

a

[POS -> CAT]

거래시작 응답전문

순번

1

내용

SIZE

속성

비고

STX

1

2

a

0x02

2

전문 길이

bcd

an

n

STX부터 CRC 까지

3

Service Code

2

“PS”

4

Message Type

2

20

5

FS

1

a

0x1C

6

알림

FS

가변

1

ksc

a

화면표시 알림 메시지

7

0x1C

8

ETX

LRC

1

a

0x03

9

1

a

LRC Data

5

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

[POS -> CAT]

토큰 생성 요청전문

순번

1

내용

SIZE

속성

a

비고

STX

1

2

0x02

2

전문 길이

Service Code

Message Type

Data

bcd

an

n

STX부터 LRC 까지

3

2

“TQ”

10

4

2

5

가변

1

ksc

a

토큰 생성 요청 전문에서는 사용하지 않음

6

FS

0x1C

7

ETX

1

a

0x03

8

LRC

1

a

LRC Data

[CAT->POS]

토큰 생성 응답전문

순번

1

내용

SIZE

속성

a

비고

STX

1

2

0x02

2

전문 길이

bcd

an

n

STX부터 CRC 까지

3

Service Code

2

“TQ”

4

Message Type

2

20

5

토큰생성 성공 여부

1

an

a

Y/N

6

FS

1

0x1C

7

VANKEY+HASH

24

1

ksc

a

TQ에서 응답 받은 VANKEY(16)+HASH(8)

8

FS

1C

9

카드정보

FS

가변

1

5-2. 카드정보 참고

10

11

12

13

14

a

ksc

a

0x1C

알림

FS

가변

1

에러코드 + RS(0x1E) + 화면표시 알림 메시지

1C

ETX

LRC

1

a

0x03

1

a

LRC Data

6

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

[POS -> CAT]

토큰 승인 요청전문

순번

1

내용

SIZE

1

속성

a

비고

STX

0x02

2

전문 길이

Service Code

Message Type

거래금액

FS

2

bcd

an

n

STX부터 CRC 까지

2

2

“D8”

10

3

2

4

9

n

거래금액 ( ex. 1000원 -> 0x31,0x30,0x30,0x30 )

5

1

a

0x1C

6

VANKEY+HASH

FS

24

1

ksc

a

TQ에서 응답 받은 VANKEY(16)+HASH(8)

7

0x1C

8

알림

가변

1

ksc

A

판매 상품 관련 결제단말기 출력 메시지

9

ETX

0x03

10

LRC

1

a

LRC Data

[CAT->POS]

토큰 승인 응답전문

순번

1

내용

SIZE

속성

a

비고

STX

1

2

0x02

2

전문 길이

bcd

an

N

STX부터 CRC 까지

3

Service Code

2

“D8”

4

Message Type

2

20

5

토큰 승인 성공 여부

1

an

a

Y/N

6

FS

1

0x1C

7

승인번호

FS

8

an

a

승인번호

8

1

1C

9

카드정보

FS

가변

1

5-2. 카드정보 참고

10

11

12

13

14

a

a

0x1C

VANKEY

FS

16

1

수신 VANKEY(16)

a

0x1C

알림

FS

가변

1

ksc

a

에러코드 + RS(0x1E) + 화면표시 알림 메시지

1C

7

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

15

16

ETX

LRC

1

1

a

a

0x03

LRC Data

[POS -> CAT]

토큰 취소 요청전문

순번

1

내용

SIZE

1

속성

a

비고

STX

0x02

2

전문 길이

Service Code

Message Type

거래금액

FS

2

bcd

an

n

STX부터 CRC 까지

2

2

“D9”

10

3

2

4

9

n

거래금액 ( ex. 1000원 -> 0x31,0x30,0x30,0x30 )

5

1

a

0x1C

6

원승인번호

FS

8

an

a

원승인번호

7

1

0x1C

8

원거래일자

FS

6

n

취소 시 원 거래에 대한 거래일자 (YYMMDD)

9

1

a

0x1C

10

11

12

VANKEY+HASH

ETX

24

1

ksc

A

TQ에서 응답 받은 VANKEY(16)+HASH(8)

0x03

LRC

1

a

LRC Data

취소시 사용되는 VANKEY, HASH 데이터는 취소하려는 승인번호 거래에 사용한 데이터 여야함

? 취소하려는 승인번호 거래에 사용된 VANKEY, HASH 와 다른 새로 발급받은 VANKEY,

HASH데이터 취소 불가.

[CAT->POS]

토큰 취소 응답

순번

내용

SIZE

속성

a

비고

1

2

3

4

5

6

7

STX

1

2

0x02

전문 길이

bcd

an

N

STX부터 CRC 까지

Service Code

Message Type

토큰 취소 성공 여부

FS

2

“D9”

2

20

1

an

a

Y/N

1

0x1C

카드정보

가변

5-2. 카드정보 참고

8

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

8

FS

VANKEY

1

16

1

a

a

0x1C

9

수신 VANKEY(16)

0x1C

10

11

12

13

14

FS

a

알림

FS

가변

1

ksc

A

에러코드 + RS(0x1E) + 화면표시 알림 메시지

1C

ETX

LRC

1

a

0x03

1

a

LRC Data

9

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

[CAT -> POS]

RF 사원증 확인 요청전문 (응답전문 없음)

순번

1

내용

SIZE

1

속성

a

비고

STX

0x02

2

전문 길이

Service Code

Message Type

Data

2

bcd

an

n

STX부터 LRC 까지

3

2

“PR”

4

2

10

5

10

1

an

a

RF CARD UID

0x1C

6

FS

7

ETX

1

a

0x03

8

LRC

1

a

LRC Data

10

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

[CAT -> POS]

삼성페이 거래시작 요청전문

순번

내용

SIZE

1

속성

a

비고

1

2

2

3

4

5

6

STX

0x02

전문 길이

Service Code

Message Type

FS

2

bcd

an

n

STX부터 CRC 까지

2

“PA”

2

10

1

a

0x1C

0x03

LRC Data

ETX

1

a

LRC

1

a

[POS -> CAT]

삼성페이 거래시작 응답전문

순번

1

내용

SIZE

속성

비고

STX

1

2

a

0x02

2

전문 길이

bcd

an

n

STX부터 CRC 까지

3

Service Code

2

“PA”

4

Message Type

2

20

5

FS

1

a

0x1C

6

알림

FS

가변

1

ksc

a

화면표시 알림 메시지

7

0x1C

8

ETX

LRC

1

a

0x03

9

1

a

LRC Data

11

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

[POS -> CAT]

삼성페이 신용승인 요청전문

순번

1

내용

SIZE

속성

a

비고

STX

1

2

0x02

2

전문 길이

Service Code

Message Type

거래금액

FS

bcd

an

n

STX부터 CRC 까지

2

2

“D1”

10

3

2

4

9

n

거래금액 ( ex. 1000원 -> 0x31,0x30,0x30,0x30 )

5

1

a

0x1C

6

거래구분

FS

1

n

‘0’: 선승인 ‘1’ 구매한 제품 금액 승인

7

1

a

0x1C

8

알림

가변

1

ksc

a

판매 상품 관련 결제단말기 출력 메시지

9

ETX

0x03

10

LRC

1

a

LRC Data

[CAT->POS]

삼성페이 신용승인 응답전문

순번

1

내용

SIZE

속성

a

비고

STX

1

2

0x02

2

전문 길이

bcd

an

N

STX부터 CRC 까지

3

Service Code

2

“D1”

4

Message Type

2

20

5

신용 승인 성공 여부

1

an

a

Y/N

6

FS

1

0x1C

7

승인번호

FS

8

an

a

승인번호

8

1

0x1C

9

VANKEY

FS

16

1

an

a

"VANKEY:" 취소고유번호

10

11

12

13

14

1C

카드정보

FS

가변

1

5-2. 카드정보 참고

a

ksc

a

1C

알림

FS

가변

1

에러코드 + RS(0x1E) + 화면표시 알림 메시지

1C

12

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

15

14

ETX

LRC

1

1

a

a

0x03

LRC Data

[POS -> CAT]

삼성페이 신용취소 요청전문

순번

1

내용

SIZE

1

속성

a

비고

STX

0x02

2

전문 길이

Service Code

Message Type

거래금액

FS

2

bcd

an

n

STX부터 CRC 까지

2

2

“D7”

10

3

2

4

9

n

거래금액 ( ex. 1000원 -> 0x31,0x30,0x30,0x30 )

5

1

a

0x1C

6

원승인번호

FS

8

an

a

원승인번호

7

1

0x1C

8

원거래일자

FS

6

n

취소 시 원 거래에 대한 거래일자 (YYMMDD)

9

1

a

0x1C

10

9

VANKEY

FS

16

1

an

a

D1에서 응답 받은 VANKEY 취소고유번호

0x1C

11

12

ETX

1

A

0x03

LRC

1

a

LRC Data

[CAT->POS]

삼성페이 신용취소 응답

순번

내용

SIZE

속성

a

비고

1

2

3

4

5

6

7

STX

1

2

0x02

전문 길이

bcd

an

N

STX부터 CRC 까지

Service Code

Message Type

신용 취소 성공 여부

FS

2

“D7”

2

20

1

an

a

Y/N

1

0x1C

카드정보

가변

5-2. 카드정보 참고

13

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

8

FS

VANKEY

1

16

1

a

a

0x1C

9

수신 VANKEY(16)

0x1C

10

11

12

13

14

FS

a

알림

FS

가변

1

ksc

A

에러코드 + RS(0x1E) + 화면표시 알림 메시지

1C

ETX

LRC

1

a

0x03

1

a

LRC Data

[POS -> CAT]

단말기 상태 확인 요청전문

순번

1

내용

SIZE

속성

비고

STX

1

2

a

bcd

an

n

0x02

2

전문 길이

Service Code

Message Type

알림

STX부터 CRC 까지

2

2

“PC”

3

2

10

4

가변

1

Ksc

a

사용중지 메시지

0x1C

5

FS

6

ETX

1

a

0x03

7

LRC

1

a

LRC Data

[CAT -> POS]

단말기 상태 확인 응답전문

순번

1

내용

SIZE

속성

비고

STX

1

2

2

2

1

1

1

1

a

0x02

2

전문 길이

Service Code

Message Type

상태값

bcd

an

n

STX부터 CRC 까지

3

“PC”

20

4

5

a

단말기 상태 ( 5-1 단말기상태 응답코드 참고’ )

9

FS

a

0x1C

10

11

ETX

a

0x03

LRC

a

LRC Data

14

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

작성일 2026-01-05

작성자 강상호

작성부서

SW

MODEL

5-1. 응답코드

토큰생성 / 삼성페이 승인 요청 에러코드

코드

값

세부설명

RC\_SUCCESS

RC\_TiMEOUT

RC\_CANCEL

0x00

0xB0

0xB1

0xB2

성공

TIMEOUT(단말기 설정 시간 내 카드 미인식)

단말기 취소

RC\_NOT\_CONDITION

거래 조건이 맞지 않음(삼성페이 선택 후 IC카드

삽입)

RC\_FORMAT\_ERROR

RC\_CAT\_RUNNING

RC\_ERROR\_RF

0xB3

0xB4

0xB5

0XB6

0xC0

0xC1

0xFF

전문 오류

단말기 다른 명령어 처리 중

RF 카드 인식 오류

RC\_ERROR\_VAN

RC\_ERROR\_POS

RC\_NETWORK\_ERROR

RC\_ERROR

VAN서버 에러 응답 오류

POS 고장으로 인한 사용중지 상태

네트워크 에러(Ping test 실패)

IC CHIP 오류 등 기타 오류

5-2. 카드정보

순번

내용

SIZE

속성

an

비고

전표일련번로 거래값이 존재할 경우 DDC 집계건수에

1

전표일련번호

가변

추가.

2

3

RS

1

3

a

n

0x1E

매입사코드

RS

카드 매입사 코드

0x1E

4

1

a

5

매입사명

RS

가변

1

ksc

a

매입사 명

0x1E

6

7

발급사코드

RS

3

n

발급사코드

0x1E

8

1

a

9

발급사명

RS

가변

1

ksc

a

발급사 명

0x1E

10

11

가맹점번호

가변

n

가맹점번호

15

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

6. 예제

VANKEY, HASH, 원승인번호, 원거래일자 등은 임의로 만든 데이터

실거래에서는 VAN Server를 통해 수신 받아야 하는 데이터

? 예제 데이터는 참고용 실 결제x

아래 예제용 전문은 단단위 테스트를 위한 전문이며, 거래흐름도 순서와 상관 없습니다.

거래시작 요청 ( CAT -> POS )

02 00 10 50 53 31 30 1C 03 0D

요청 ( POS -> CAT )

02 00 10 54 51 31 30 1c 03 0B

성인인증 응답 ( CAT -> POS )

02 00 12 41 43 32 30 59 1C 1C 03 48

토큰승인요청( POS -> CAT )

02 00 38 44 38 31 30 35 30 30 30 1C 30 33 32 35 30 31 35 36 31 38 36 32 31 33 34 39 37 34 39

31 32 38 31 62 03 09

토큰승인취소 요청 ( POS-> CAT )

02 00 54 44 39 31 30 35 30 30 30 1C 30 30 31 31 38 35 33 39 1c 32 34 31 31 32 30 1c 30 33 32

35 30 31 35 36 31 38 36 32 31 33 34 39 37 34 39 31 32 38 31 62 03 67

삼성페이 거래시작 요청 ( CAT -> POS )

02 00 10 50 41 31 30 1C 03 1F

삼성페이 승인요청( POS -> CAT )

02 00 16 44 31 31 30 35 35 35 35 1C 01 1c 03 60?(선승인보증금)

02 00 16 44 31 31 30 35 35 35 35 1C 00 1c 03 61?(실결제)

삼성페이 승인취소 요청 ( POS-> CAT )

02 00 47 44 37 31 30 31 30 30 34 1C 31 34 31 37 31 39 33 35 1C 32 35 30 32 31 34 1c 30 30 34

35 30 31 31 36 32 33 37 35 30 32 31 33 1C 03 3A

16

![](data:image/png;base64...)

TCP-40 토큰거래

TITLE

TCP-40 토큰거래

TCP-40

Rev 1.0.0.2

SW

작성일 2026-01-05

작성자 강상호

작성부서

MODEL

단말기 상태확인 요청(POS -> CAT)

상태확인

02 00 10 50 43 31 30 1c 03 1d

사용중지메시지(“사용불가 상태입니다”)

02 00 29 50 43 31 30 bb e7 bf eb ba d2 b0 a1 20 bb f3 c5 c2 c0 d4 b4 cf b4 d9 1c 03 38

17
