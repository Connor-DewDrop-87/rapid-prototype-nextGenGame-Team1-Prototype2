using UnityEngine;
// Reference used: https://gamedevbeginner.com/how-to-make-countdown-timer-in-unity-minutes-seconds/
public class Timer : MonoBehaviour
{
    public float timeLeft = 300f;
    public bool timerRunning = true;

    // Update is called once per frame
    void Update()
    {
        if (timerRunning)
        {
            if (timeLeft > 0)
            {
                timeLeft -= Time.deltaTime;
            }
            else
            {
                Debug.Log("Time has run out!");
                timeLeft = 0;
                timerRunning = false;
            }
        }

    }

    public string GetTimeText()
    {
        float minutes = Mathf.FloorToInt(timeLeft / 60);
        float seconds = Mathf.FloorToInt(timeLeft % 60);

        return string.Format("{0:0}:{1:00}", minutes, seconds);
    }
}
