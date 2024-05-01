from powder_settings import PowderProtocol, PowderSettings

default_ps = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 50,
                                percent_target = 0.75,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 5,
                                opening_deg = 30,
                                percent_target = 0.50,
                                max_growth = 1.25,
                                amplitude = 75
                                ),
                            slow_settings = PowderSettings(
                                thresh = 3,
                                opening_deg = 25,
                                percent_target = 1,
                                max_growth = 1.1,
                                shut_valve = False
                                ),
                            ultra_slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 0,
                                percent_target = 0.7,
                                max_growth = 1.1,
                                amplitude = 50,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )

alconox = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 40,
                                percent_target = 0.75,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 5,
                                opening_deg = 30,
                                percent_target = 0.50,
                                max_growth = 1.1
                                ),
                            slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 30,
                                percent_target = 1,
                                max_growth = 1.1,
                                shut_valve = False
                                ),
                            ultra_slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 5,
                                percent_target = 0.7,
                                max_growth = 1.1,
                                amplitude = 50,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )
LiOAc = PowderProtocol(tol = 0.2,
                            fast_settings = PowderSettings(
                                opening_deg = 45,
                                percent_target = 0.9,
                                max_growth = 3
                                ),
                            med_settings = PowderSettings(
                                thresh = 50,
                                opening_deg = 40,
                                percent_target = 0.9,
                                max_growth = 1.3
                                ),
                            slow_settings = PowderSettings(
                                thresh = 10,
                                opening_deg = 28,
                                percent_target = 0.8,
                                max_growth = 1.1,
                                amplitude = 80,
                                shut_valve = False
                                ),
                            ultra_slow_settings = PowderSettings(
                                thresh = 2,
                                opening_deg = 26,
                                percent_target = 0.8,
                                max_growth = 1.1,
                                amplitude = 65,
                                shut_valve = False
                                ),
                             scale_delay=1
                            )