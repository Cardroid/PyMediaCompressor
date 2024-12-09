# PyMediaCompressor

> FFmpeg 파이썬 래퍼를 사용한 간단한 미디어 압축기

### 설명

FFmpeg를 사용하여 미디어를 인코딩합니다.  
느리지만 압축률이 높은 preset을 설정하여 CPU 사용량이 매우 높지만, 높은 압축률로 미디어를 인코딩할 수 있습니다.  
해당 프로젝트는 FFmpeg를 잘 알지 못해도 사용할 수 있도록 개발되었습니다.

> ubuntu 20.04 서버, windows 11 에서 테스트 되었습니다.

#### 인코더의 선택 가능한 옵션

1. 퀄리티 값 (crf) (값의 범위 0 ~ 51, 0 = 무손실, 51 = 최악의 품질) (기본값 = [h.264 = 23, h.265 = 28])
2. 코덱 (h.264, h.265)
3. 세로 픽셀 수 (가로는 비율에 맞게 자동 조절) (기본값 = 1440)
4. 하드웨어 가속 디코딩 (cuda만 지원)

#### 주의 사항

1. 미디어의 "video 또는 audio가 아닌 스트림 (자막, 챕터 등)" 또는 "메타데이터"가 제거될 수 있습니다.

2. 썸네일 이미지가 제거됩니다.

3. 미디어의 Comment 메타데이터 마지막 부분에 다음의 정보가 기록됩니다.
    - 프로젝트 테그 헤더 (이미 압축 처리가 되었는가 판단용으로 사용됨)
    - 해당 프로젝트 메타데이터 버전
    - 입력파일의 크기
    - 입력파일의 MD5 해시 정보
    - 인코딩 날짜

### 설치

```
pip install git+https://github.com/Cardroid/PyMediaCompressor.git
```

### 사용 방법

```
encode -h
```

```
usage: encode [-h]
              -i INPUT
              [-o OUTPUT]
              [-r]
              [-p]
              [-e {overwrite,skip,numbering}]
              [--sort_mode]
              [-s]
              [-f]
              [-c {h.264,h.265}]
              [--crf {-1~51}]
              [--scan]
              [--height HEIGHT]
              [--cuda]
              [--log-level {debug,info,warning,error,critical}]
              [--log-mode {c,f,cf,console,file,consolefile}]
              [--log-path LOG_PATH]

미디어를 압축 인코딩합니다.

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT              하나 이상의 입력 소스 파일 및 디렉토리 경로
  -o OUTPUT             출력 디렉토리 경로
  -r, --replace         원본 파일보다 작을 경우, 원본 파일을 덮어씁니다. 아닐 경우, 출력파일이 삭제됩니다.
  -p, --size_skip       빠른 작업을 위해 인코딩 도중 출력파일 크기가 입력파일 크기보다 커지는 순간 즉시 건너뜁니다.
  -e {overwrite,skip,numbering}, --already_exists_mode {overwrite,skip,numbering}
                        출력 폴더에 같은 이름의 파일이 있을 경우, 사용할 모드.
  --sort_mode           파일 사이즈 정렬 옵션 (on = 내림차순, reverse = 오름차순)
  -s, --save_error_output
                        오류가 발생한 출력물을 제거하지 않습니다.
  -f, --force           이미 압축된 미디어 파일을 강제로, 재압축합니다.
  -c {h.264,h.265}, --codec {h.264,h.265}
                        인코더에 전달되는 비디오 코덱 옵션
  --crf {-1~51}         인코더에 전달되는 crf 값 (-1을 입력하면 코덱에 따라 기본값이 자동으로 계산됩니다.) [h.264 = 23, h.265 = 28]
  --scan                해당 옵션을 사용하면, 입력 파일을 탐색하고, 실제 압축은 하지 않습니다.
  --height HEIGHT       출력 비디오 스트림의 최대 세로 픽셀 수를 설정합니다. (가로 픽셀 수는 비율에 맞게 자동으로 계산됨)
  --cuda                CUDA 그래픽카드를 사용하여 소스 파일을 디코드합니다.
  --log-level {debug,info,warning,error,critical}
                        로그 레벨 설정
  --log-mode {c,f,cf,console,file,consolefile}
                        로그 출력 모드
  --log-path LOG_PATH   로그 출력 경로
```

### TODO

-   [ ] 인코딩 후 스트림 무결성 검사
